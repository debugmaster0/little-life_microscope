import cv2

for i in range(10):
    cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)  # macOS backend
    ok = cap.isOpened()
    print(i, "OK" if ok else "no")
    if ok:
        ret, frame = cap.read()
        print("  read:", ret, "shape:", None if frame is None else frame.shape)
    cap.release()
