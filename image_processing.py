from azure.cognitiveservices.vision.computervision import ComputerVisionClient
from azure.cognitiveservices.vision.computervision.models import OperationStatusCodes
from msrest.authentication import CognitiveServicesCredentials
from msrest.exceptions import HttpOperationError
import time
import json
import io
from PIL import Image

subscription_key = "0bff772aff8f4850a2d61c6fd8bbadf5"
endpoint = "https://mithun.cognitiveservices.azure.com/"
computervision_client = ComputerVisionClient(endpoint, CognitiveServicesCredentials(subscription_key))

def perform_ocr(image_stream):
    while True:
        try:
            ocr_result = computervision_client.read_in_stream(image_stream, raw=True)
            break
        except HttpOperationError as e:
            if "429" in str(e):
                print("Rate limit exceeded. Waiting for a while before retrying...")
                time.sleep(30)  # Wait for 30 seconds before retrying
            else:
                raise e

    operation_location = ocr_result.headers["Operation-Location"]
    operation_id = operation_location.split("/")[-1]

    while True:
        result = computervision_client.get_read_result(operation_id)
        if result.status not in ['notStarted', 'running']:
            break
        time.sleep(1)

    detected_text = []
    if result.status == OperationStatusCodes.succeeded:
        for text_result in result.analyze_result.read_results:
            for line in text_result.lines:
                detected_text.append({
                    "text": line.text,
                    "bounding_box": line.bounding_box
                })
    return detected_text

def process_image(image_path):
    with Image.open(image_path) as img:
        width, height = img.size
        left_box = (0, 0, width // 2, height)
        right_box = (width // 2, 0, width, height)

        all_detected_text = []
        for box in [left_box, right_box]:
            column_img = img.crop(box)
            with io.BytesIO() as image_stream:
                column_img.save(image_stream, format='JPEG')
                image_stream.seek(0)
                detected_text = perform_ocr(image_stream)
                all_detected_text.extend([item['text'] for item in detected_text])
    
    return "\n".join(all_detected_text)

def ocr_local_image_full(image_path, output_json_file, output_text_file, subscription_key, endpoint):
    # Initialize the Computer Vision client
    computervision_client = ComputerVisionClient(endpoint, CognitiveServicesCredentials(subscription_key))

    # Read the image and perform OCR
    with open(image_path, "rb") as image_stream:
        ocr_result = computervision_client.read_in_stream(image_stream, raw=True)
    
    operation_location = ocr_result.headers["Operation-Location"]
    operation_id = operation_location.split("/")[-1]
    
    # Wait for the operation to complete
    while True:
        result = computervision_client.get_read_result(operation_id)
        if result.status not in ['notStarted', 'running']:
            break
        time.sleep(1)

    # Collect the detected text with positions
    detected_text = []
    if result.status == OperationStatusCodes.succeeded:
        for text_result in result.analyze_result.read_results:
            for line in text_result.lines:
                detected_text.append({
                    "text": line.text,
                    "bounding_box": line.bounding_box
                })

    # Read the existing JSON file
    try:
        with open(output_json_file, "r", encoding='utf-8') as file:
            data = json.load(file)
    except FileNotFoundError:
        data = []

    # Append the new detected text to the JSON data
    data.append({
        "image_path": image_path,
        "detected_text": detected_text
    })

    # Write the updated data back to the JSON file
    with open(output_json_file, "w", encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

    # Write the detected text to a text file
    with open(output_text_file, "w", encoding='utf-8') as file:
        file.write("\n".join([item['text'] for item in detected_text]))
