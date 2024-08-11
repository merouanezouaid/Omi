from flask import Flask, request, jsonify
import os
from langchain_openai import ChatOpenAI
from multion.client import MultiOn
import redis
import uuid


app = Flask(__name__)

# Initialize MultiOn client
multion = MultiOn(api_key="9f9219f3da4c4ac6a5b7bec605e3091e")

# Initialize Redis client
r = redis.Redis(
    host=os.getenv('REDIS_HOST'),
    port=os.getenv('REDIS_PORT'),
    password=os.getenv('REDIS_PASSWORD')
)

# Utility functions
def append_segment_to_transcript(uid: str, session_id: str, new_segments: list[dict]):
    key = f'transcript:{uid}:{session_id}'
    segments = r.get(key)
    if not segments:
        segments = []
    else:
        segments = eval(segments)
    segments.extend(new_segments)
    segments = sorted(segments, key=lambda x: x['start'])
    r.set(key, str(segments))
    return segments

def remove_transcript(uid: str, session_id: str):
    r.delete(f'transcript:{uid}:{session_id}')

def clean_all_transcripts_except(uid: str, session_id: str):
    for key in r.scan_iter(f'transcript:{uid}:*'):
        if key.decode().split(':')[2] != session_id:
            r.delete(key)

def retrieve_food_order(transcript: str):
    chat = ChatOpenAI(model='gpt-4', temperature=0)
    response = chat.invoke(f'''The following is the transcript of a conversation.
    {transcript}
    Your task is to determine if the speakers mentioned wanting to order food from DoorDash.
    If they did, provide the food items they want to order and the restaurant name if mentioned.
    Only include items if they specifically said they want to order from DoorDash.''')
    print('Food order:', response.content)
    return response.content

def place_doordash_order(food_type: str):
    response = multion.browse(
        cmd=f"Order {food_type} food from DoorDash. Choose a well-rated restaurant, select appropriate items, and proceed to checkout. Stop at the payment page.",
        url="https://www.doordash.com/home/?newUser=true",
        local=True,
    )
    return {
        "status": "Order prepared",
        "message": response.message,
        "url": response.url
    }

@app.route('/endpoint/', methods=['POST'])
def get_post_data(uid):
    data = request.get_json()
    print(data)

    if not data or 'segments' not in data:
        return jsonify({'error': 'Invalid data format'}), 400

    session_id = data['session_id']
    new_segments = data['segments']

    clean_all_transcripts_except(uid, session_id)
    transcript = append_segment_to_transcript(uid, session_id, new_segments)

    # print(transcript)

    food_order = retrieve_food_order(str(transcript))
    # food_order = "pizza"

    if food_order:
        try:
            order_result = place_doordash_order(food_order)
            if order_result:
                # remove_transcript(uid, session_id)
                print(order_result)
                return jsonify({
                    'message': f'DoorDash order prepared for {food_order}',
                    'order_details': order_result
                }), 200
        except Exception as e:
            return jsonify({'error': f'Failed to prepare order: {str(e)}'}), 500
    else:
        return jsonify({'message': 'No DoorDash order detected'}), 200

# if __name__ == '__main__':
#     # app.run(debug=True)
#     place_doordash_order("pizza")