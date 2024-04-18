import os, cv2
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import scipy
from flask import Flask, render_template, request

import tensorflow as tf
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.applications.mobilenet import preprocess_input
from tensorflow.keras.layers import Dense, Conv2D, MaxPooling2D, Flatten, Dropout
from flask import Flask, render_template, request
from tensorflow.keras.models import load_model

# Create a new graph
graph = tf.Graph()

app = Flask(__name__)
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

def get_model():
    global loadModel
    loadModel = Sequential([
                            Conv2D(32, (3, 3), activation='relu', input_shape=(150, 150, 3)),
                            MaxPooling2D(2, 2),
                            Conv2D(64, (3, 3), activation='relu'),
                            MaxPooling2D(2, 2),
                            Conv2D(128, (3, 3), activation='relu'),
                            MaxPooling2D(2, 2),
                            Flatten(),
                            Dense(512, activation='relu'),
                            Dropout(0.5),
                            Dense(1, activation='sigmoid') # Use 'softmax' if you have more than two classes
                        ])

    loadModel.compile(loss='binary_crossentropy', optimizer='adam', metrics=['accuracy'])
    
    # load pre-trained model
    loadModel.load_weights("pneumonia-prediction-webapp-master/model/model.h5")
    

    print("model_loaded")


def plot_mobilenet_CAM(image, image_preprocessed, ax, model, all_amp_layer_weights):
    ax.imshow(image, alpha=0.5)
    CAM = mobilenet_CAM(image_preprocessed, model, all_amp_layer_weights)
    ax.imshow(CAM, cmap="jet", alpha=0.5)
    return CAM


def get_mobileNet(model):
    all_amp_layer_weights = model.layers[-1].get_weights()[0]
    plot_model = Model(inputs=model.input, outputs=(model.layers[-4].output, model.layers[-1].output))
    return plot_model, all_amp_layer_weights


def mobilenet_CAM(image, model, all_amp_layer_weights):
    with graph.as_default():
        last_conv_output, pred_vec = model.predict(image)
    last_conv_output = np.squeeze(last_conv_output)
    pred = np.argmax(pred_vec, axis=1)
    mat_for_mult = scipy.ndimage.zoom(last_conv_output, (32, 32, 1), order=1)
    amp_layer_weights = all_amp_layer_weights[:, pred]
    final_output = np.dot(mat_for_mult.reshape((224 * 224, 1024)), amp_layer_weights).reshape(224, 224)
    return final_output


# ////////////////////////////
# ROUTES
# ////////////////////////////

@app.route("/")
def index():
    return render_template("index.html")

# Enforce eager execution
tf.config.run_functions_eagerly(True)
@app.route("/diagnostic", methods=['GET', 'POST'])
def diagnostic():
    if request.method == 'POST':
        target = os.path.join(APP_ROOT, 'static/xray/')
        os.makedirs(target, exist_ok=True)
        file = request.files.get("file")
        filename = file.filename
        destination = os.path.join(target, filename)
        file.save(destination)

        image = cv2.cvtColor(cv2.imread(destination), cv2.COLOR_BGR2RGB)
        image = cv2.resize(image, (150, 150))
        image_preprocessed = preprocess_input(np.array([image]))
        image_preprocessed = image_preprocessed[0]

        pred = loadModel.predict(np.expand_dims(image_preprocessed, axis=0))
        prediction = int(np.argmax(pred, axis=1)[0])

        if prediction:
            plot_dest = os.path.join(target, "result.png")
            mob_model, all_amp_layer_weights = get_mobileNet(loadModel)
            fig, ax = plt.subplots()
            plot_mobilenet_CAM(image, image_preprocessed, ax, mob_model, all_amp_layer_weights)
            plt.savefig(plot_dest, bbox_inches='tight')

        return render_template("result.html", prediction=prediction, filename=filename)
    else:
        return render_template("diagnostic.html")
MODEL_PATH = 'pneumonia-prediction-webapp-master/model/model.h5'  # Update the path
model = load_model(MODEL_PATH)
def preprocess_image(image_path):
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError("Unable to load image at " + image_path)
    image = cv2.resize(image, (150, 150))
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    image = image / 255.0
    image = np.expand_dims(image, axis=0)
    return image

@app.route("/upload", methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        target = os.path.join(APP_ROOT, 'static/xray/')
        os.makedirs(target, exist_ok=True)
        file = request.files['file']
        filename = file.filename
        destination = os.path.join(target, filename)
        file.save(destination)

        try:
            image_preprocessed = preprocess_image(destination)
            prediction = model.predict(image_preprocessed)
            is_pneumonia = prediction[0][0] > 0.5  # Assuming binary classification [pneumonia or not]

            plot_dest = os.path.join(target, "result.png")
            # Assuming you have a function to generate and save the result image
            # You need to integrate or modify your existing plot_mobilenet_CAM function accordingly

            return render_template("result.html", prediction=is_pneumonia, filename=filename, result_filename="result.png")
        except Exception as e:
            return f"An error occurred: {str(e)}"

    else:
        return render_template("upload.html")

# Assuming other functions are defined elsewhere

if __name__ == "__main__":
    get_model()
    app.run(debug=True)