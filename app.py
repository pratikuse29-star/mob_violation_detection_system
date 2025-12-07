# =============================================================
# 🧠  MODULAR MOB VIOLATION DETECTION (PhD Module-wise)
# =============================================================
from flask import Flask, render_template, request, send_from_directory, jsonify, Response, redirect, url_for
from ultralytics import YOLO
import torch, cv2, os, uuid, json, time
import numpy as np

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['RESULT_FOLDER'] = 'static/results'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['RESULT_FOLDER'], exist_ok=True)

# -------------------------------------------------------------
# Load models from the main project directory to save space
# -------------------------------------------------------------
MODEL_DIR = "models"

print("Loading models...")
models = {
    "fire":    torch.hub.load('ultralytics/yolov5', 'custom',
                               path=os.path.join(MODEL_DIR, 'fire.pt'), trust_repo=True),
    "placard": torch.hub.load('ultralytics/yolov5', 'custom',
                               path=os.path.join(MODEL_DIR, 'placard.pt'), trust_repo=True),
    "weapon":  torch.hub.load('ultralytics/yolov5', 'custom',
                               path=os.path.join(MODEL_DIR, 'weapon.pt'), trust_repo=True),
    "stick":   YOLO(os.path.join(MODEL_DIR, 'stick.pt')),
    "person":  YOLO(os.path.join(MODEL_DIR, 'person.pt'))
}
print("Models loaded.")

# Color scheme
COLORS = {
    "person": (0, 255, 0),      # Green
    "fire": (0, 0, 255),        # Red
    "weapon": (255, 0, 0),      # Blue
    "stick": (255, 165, 0),     # Orange
    "placard": (255, 255, 0)    # Yellow
}

# Global dictionary to store processing status and results
processing_status = {}

def classify_mob(counts):
    crowd, violence, unrest = counts["person"], counts["weapon"] + counts["fire"], counts["stick"] + counts["placard"]
    if violence > 0 and crowd >= 3:
        return "Violent Mob", "danger"
    elif unrest > 0 and crowd >= 3:
        return "Restless Crowd", "warning"
    else:
        return "Peaceful Crowd", "success"

# -------------------------------------------------------------
# Generator: Process video with MODULE FILTER
# -------------------------------------------------------------
def generate_frames(video_path, uid, selected_module):
    cap = cv2.VideoCapture(video_path)
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    output_filename = f"annotated_{uid}.mp4"
    output_path = os.path.join(app.config['RESULT_FOLDER'], output_filename)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    detection_timeline = []
    total_counts = {"person":0, "stick":0, "weapon":0, "fire":0, "placard":0}
    
    frame_idx = 0
    
    processing_status[uid] = {
        'status': 'processing',
        'total_frames': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        'current_frame': 0,
        'module': selected_module
    }
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_detections = []
        frame_counts = {"person":0, "stick":0, "weapon":0, "fire":0, "placard":0}
        
        # --- MODULE LOGIC ---
        # Only run detection if the module matches or is 'all'
        
        # Group 1: YOLOv5 models (fire, placard, weapon)
        for name in ["fire", "placard", "weapon"]:
            if selected_module == 'all' or selected_module == name:
                results = models[name](frame)
                for *box, conf, cls in results.xyxy[0]:
                    if models[name].names[int(cls)].lower() == name:
                        x1, y1, x2, y2 = [int(x) for x in box]
                        frame_detections.append({
                            'bbox': [x1, y1, x2, y2],
                            'label': name,
                            'confidence': float(conf)
                        })
                        frame_counts[name] += 1
                        
                        color = COLORS[name]
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                        label_text = f"{name}: {conf:.2f}"
                        cv2.putText(frame, label_text, (x1, y1-10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Group 2: YOLOv8 models (stick, person)
        for name in ["stick", "person"]:
            if selected_module == 'all' or selected_module == name:
                results = models[name](frame, conf=0.4, verbose=False)
                if len(results[0].boxes) > 0:
                    for box in results[0].boxes:
                        xyxy = box.xyxy[0].cpu().numpy()
                        conf = box.conf[0].cpu().numpy()
                        x1, y1, x2, y2 = [int(x) for x in xyxy]
                        
                        frame_detections.append({
                            'bbox': [x1, y1, x2, y2],
                            'label': name,
                            'confidence': float(conf)
                        })
                        frame_counts[name] += 1
                        
                        color = COLORS[name]
                        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                        label_text = f"{name}: {conf:.2f}"
                        cv2.putText(frame, label_text, (x1, y1-10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        # Write annotated frame
        out.write(frame)
        
        detection_timeline.append({
            'frame': frame_idx,
            'time': frame_idx / fps,
            'detections': frame_detections,
            'counts': frame_counts
        })
        
        for key in total_counts:
            if frame_counts[key] > 0:
                total_counts[key] = max(total_counts[key], frame_counts[key])
        
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        
        processing_status[uid]['current_frame'] = frame_idx
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
        frame_idx += 1
    
    cap.release()
    out.release()
    
    mob_state, alert = classify_mob(total_counts)
    timeline_file = f"timeline_{uid}.json"
    with open(os.path.join(app.config['RESULT_FOLDER'], timeline_file), 'w') as f:
        json.dump(detection_timeline, f)
        
    processing_status[uid].update({
        'status': 'completed',
        'annotated_video': output_filename,
        'timeline_file': timeline_file,
        'mob_state': mob_state,
        'alert': alert,
        'counts': total_counts
    })

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST' and 'video' in request.files:
        f = request.files['video']
        module = request.form.get('module', 'all')
        
        if f.filename == '':
            return render_template('index.html', message="No video selected")
        
        uid = uuid.uuid4().hex
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{uid}_{f.filename}")
        f.save(save_path)
        
        # Store module choice in status
        processing_status[uid] = {'status': 'pending', 'module': module}
        
        return jsonify({'uid': uid, 'filename': f.filename, 'module': module})
    
    return render_template('index.html')

@app.route('/video_feed/<uid>')
def video_feed(uid):
    # Retrieve the module selection for this UID
    module = processing_status.get(uid, {}).get('module', 'all')
    
    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if filename.startswith(uid):
            video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            return Response(generate_frames(video_path, uid, module),
                           mimetype='multipart/x-mixed-replace; boundary=frame')
    return "Video not found", 404

@app.route('/status/<uid>')
def get_status(uid):
    return jsonify(processing_status.get(uid, {'status': 'unknown'}))

@app.route('/result/<uid>')
def result(uid):
    if uid not in processing_status or processing_status[uid]['status'] != 'completed':
        return redirect(url_for('index'))
    
    data = processing_status[uid]
    return render_template('index.html', 
                           mode='result',
                           annotated_video=data['annotated_video'],
                           timeline_file=data['timeline_file'],
                           mob_state=data['mob_state'],
                           alert=data['alert'],
                           counts=data['counts'],
                           module=data.get('module', 'all'))

@app.route('/api/timeline/<filename>')
def get_timeline(filename):
    filepath = os.path.join(app.config['RESULT_FOLDER'], filename)
    with open(filepath, 'r') as f:
        return jsonify(json.load(f))

@app.route('/static/<path:p>')
def static_proxy(p):
    return send_from_directory('static', p)

if __name__ == "__main__":
    app.run(debug=True, port=5001) # Run on different port
