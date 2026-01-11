import cv2

INDEX = 0  # try 0, then 1, then 2

cap = cv2.VideoCapture(INDEX, cv2.CAP_AVFOUNDATION)
if not cap.isOpened():
    raise RuntimeError(f"Could not open camera index {INDEX}")

while True:
    ok, frame = cap.read()
    if not ok:
        print("read failed")
        break

    cv2.imshow(f"Camera {INDEX} (press q to quit)", frame)
    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()