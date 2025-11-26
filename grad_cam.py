import cv2
import numpy as np
import tensorflow as tf


def generate_gradcam(model, img_path, output_path):
    # Load image
    img = tf.keras.preprocessing.image.load_img(img_path, target_size=(64, 64))
    x = tf.keras.preprocessing.image.img_to_array(img)
    x = np.expand_dims(x, axis=0)

    # Last conv layer
    last_conv_layer = None
    for layer in reversed(model.layers):
        if len(layer.output_shape) == 4:
            last_conv_layer = layer.name
            break

    conv_layer = model.get_layer(last_conv_layer)

    grad_model = tf.keras.models.Model(
        [model.inputs],
        [conv_layer.output, model.output]
    )

    with tf.GradientTape() as tape:
        conv_outputs, predictions = grad_model(x)
        loss = predictions[:, 0]

    grads = tape.gradient(loss, conv_outputs)[0]
    guided_grads = grads.numpy()

    conv_outputs = conv_outputs[0].numpy()

    # Generate heatmap
    weights = np.mean(guided_grads, axis=(0, 1))
    cam = np.dot(conv_outputs, weights)

    cam = cv2.resize(cam, (256, 256))
    cam = np.maximum(cam, 0)
    cam = cam / cam.max()

    # Convert image for overlay
    original = cv2.imread(img_path)
    original = cv2.resize(original, (256, 256))

    heatmap = cv2.applyColorMap(np.uint8(255 * cam), cv2.COLORMAP_JET)
    blended = cv2.addWeighted(original, 0.6, heatmap, 0.4, 0)

    # 🔥 Find pneumonia region & draw border
    thresh = np.uint8(cam * 255)
    _, binary = cv2.threshold(thresh, 180, 255, cv2.THRESH_BINARY)

    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if len(contours) > 0:
        # Largest region
        c = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(c)

        # Draw glow border
        cv2.rectangle(blended, (x, y), (x + w, y + h), (0, 0, 255), 4)
        cv2.rectangle(blended, (x, y), (x + w, y + h), (255, 255, 255), 1)

    # Save file
    cv2.imwrite(output_path, blended)
