import os
import cv2
import mediapipe as mp
from concurrent.futures import ThreadPoolExecutor
import pandas as pd


class HandDetector:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(static_image_mode=False, max_num_hands=2, min_detection_confidence=0.5,
                                         min_tracking_confidence=0.5)
        self.mp_drawing = mp.solutions.drawing_utils

    # funkcja ta dziala dla jednej klatki
    # oznaczanie punktow, nadanie im nazw a1,a2, itp
    # zapisywanie do hand_data punktow w postaci klucz:wartosc - jest to ich polozenie wzgledem punktu 0,0 w lewym gornym rogu
    def label_points(self, image, landmarks):
        hand_data = {}
        for idx, landmark in enumerate(landmarks.landmark):
            h, w, c = image.shape
            cx, cy = int(landmark.x * w), int(landmark.y * h)
            label = f'a{idx + 1}'
            cv2.putText(image, label, (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1, cv2.LINE_AA)
            hand_data[label] = (landmark.x, landmark.y, landmark.z)
        return image, hand_data

    # oznaczanie dloni na klatce, obecnie w klatce moze byc wiecej niz jedna dlon, chyba powinnismy to ograniczyc tylko do jednej dloni
    # ta funkcja znajduje punkty na klatce i przekazuje je do funkcji ktora je oznacza i zwraca
    def detect_hands(self, frame):
        results = self.hands.process(frame)
        hand_positions = []
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                frame, hand_data = self.label_points(frame, hand_landmarks)
                hand_positions.append(hand_data)
                self.mp_drawing.draw_landmarks(frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)

        return frame, hand_positions

    def close(self):
        self.hands.close()


class VideoProcessor:
    def __init__(self):
        self.hand_detector = HandDetector()
        self.display = True

    # przetwarza filmik
    def process_video(self, video_path):
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print("Error: Cannot open video file:", video_path)
            return

        # pozycje dloni na wszystkich klatkach
        hand_positions = []
        label = str(os.path.abspath(video_path)).split("\\")[-2]

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frame_with_hands, hand_data = self.hand_detector.detect_hands(frame)
            if hand_data:
                dict = hand_data[0]
                dict['label'] = label
                hand_data = [dict]
            hand_positions.append(hand_data)

            if self.display:
                cv2.imshow('MediaPipe Hands', cv2.cvtColor(frame_with_hands, cv2.COLOR_RGB2BGR))
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        output_dir = os.path.join("Processed_Data", os.path.splitext(os.path.basename(video_path))[0])
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, 'output.csv')

        # Saving the processed data to a CSV file
        self.save_to_csv(hand_positions, output_path)
        print("Processed and data saved:", output_path)

        # w tym momencie w hand_positions znajduja sie wszystkie pozycje dloni w danym filmie
        # trzeba je teraz przetworzyc i zapisac do pliku
        # trzeba sprawdzic czy w danym elemencie hand_positions znajduje sie 21 elementow tzn, czy zaden punkt dloni nie zostal uciety np byl poza kamera

        # w tym momencie mamy punkty z jednego video z jednego folderu, chyba najlepiej najpierw przetworzyc wszystkie pliki osobno, tzn zapisywac np filmik1 z folderu A
        # do folderu Data_przetworzone/A_przetworzone/filmik1_przetworzone.csv
        # a potem polaczyc te wszystkie pliki csv w calosc
        # w csv powinno byc cos w tym stylu
        # label,a1a5(odleglosc od a1 do a5),...
        # A,0.5784,...
        # cos w tym formacie

        print("Processed: ", video_path)
        cv2.destroyAllWindows()
        cap.release()

    def save_to_csv(self, hand_positions, output_path):
        if not hand_positions:
            print("No hand positions data to save.")
            return

        # Creating DataFrame to save as CSV
        df = pd.DataFrame([pos for frame_data in hand_positions for pos in frame_data])
        df.to_csv(output_path, index=False)

        print("Data saved to:", output_path)

    # przetwarza wszystkie filmiki w danym folderze
    def process_videos_in_folder(self, folder_path):
        if not os.path.exists(folder_path):
            print(f"The folder {folder_path} does not exist.")
            return

        video_files = [file for file in os.listdir(folder_path) if file.endswith(('.mp4', '.avi', '.mov'))]
        for video_file in video_files:
            video_path = os.path.join(folder_path, video_file)
            self.process_video(video_path)

    def __del__(self):
        cv2.destroyAllWindows()
        self.hand_detector.close()


# przetwarza wszystkie foldery w folderze Data
def process_folders_in_data(data_folder_path, multithreading=False):
    subfolders = [folder for folder in os.listdir(data_folder_path) if
                  os.path.isdir(os.path.join(data_folder_path, folder))]
    if multithreading:
        with ThreadPoolExecutor() as executor:
            for folder in subfolders:
                folder_path = os.path.join(data_folder_path, folder)
                executor.submit(process_folder, folder_path)
    else:
        for folder in subfolders:
            folder_path = os.path.join(data_folder_path, folder)
            process_folder(folder_path)


# przetwarzanie folderu
def process_folder(folder_path):
    video_processor = VideoProcessor()
    video_processor.process_videos_in_folder(folder_path)


def combine_csv():
    data_preprocessor_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Data_preprocessor")
    processed_data_path = os.path.join(data_preprocessor_path, "Processed_Data")

    combined_dataframe = pd.DataFrame()  # Initialize an empty DataFrame to hold all the data
    if os.path.exists(processed_data_path) and os.path.isdir(processed_data_path):
        # List all subdirectories in the 'Processed_Data'
        subdirs = [os.path.join(processed_data_path, d) for d in os.listdir(processed_data_path) if
                   os.path.isdir(os.path.join(processed_data_path, d))]
        for subdir in subdirs:
            csv_file_path = next((os.path.join(subdir, file) for file in os.listdir(subdir) if file.endswith('.csv')),
                                 None)
            if csv_file_path:
                # Read the CSV file and append it to the DataFrame
                temp_df = pd.read_csv(csv_file_path)
                combined_dataframe = pd.concat([combined_dataframe, temp_df], ignore_index=True)
    else:
        print("Processed_Data directory does not exist.")
        return

    combined_csv_path = os.path.join(processed_data_path, 'combined_data.csv')
    combined_dataframe.to_csv(combined_csv_path, index=False)
    print("Combined CSV created at:", combined_csv_path)


def main():
    data_folder_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Data")
    if os.path.exists(data_folder_path):
        print("Processing videos in the specified folder:")
        process_folders_in_data(data_folder_path, multithreading=False)

        combine_csv()

    else:
        print("The specified folder does not exist.")


if __name__ == "__main__":
    main()
