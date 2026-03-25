### **Instructions for Local Webcam Inspection**

**1. Prerequisites**

*   **Python:** Ensure you have Python 3 installed on your system.
*   **OpenCV:** You need the `opencv-python` library. If you haven't already, install it by opening your command prompt or terminal and running:
    ```bash
    pip install opencv-python numpy
    ```

**2. Ensure the Script is Ready**

*   Confirm that the `camera_inspector.py` file is located in your `C:\dev` directory. This is where you previously asked me to save it.

**3. Run the Script**

*   Open your command prompt or terminal.
*   Navigate to the `C:\dev` directory using the `cd` command:
    ```bash
    cd C:\dev
    ```
*   Execute the Python script:
    ```bash
    python camera_inspector.py
    ```

**4. Interact with the Inspector**

*   A window should appear, showing the live feed from your default webcam.
*   Text overlays on the video will display:
    *   **Blur Score:** A numerical value indicating sharpness. A lower value means more blur. It will turn **red** if `BLUR_THRESHOLD` is exceeded.
    *   **Frozen Status:** It will count how many consecutive frames have been identical. It will turn **red** and declare "FROZEN!" if the `FROZEN_FRAME_COUNT_THRESHOLD` is reached.
*   **To Quit:** Press the `q` key while the inspection window is active.

**5. Troubleshooting (Optional)**

*   **"Error: Could not open camera source 0."**: Your default camera might not be index `0`. You can try changing the `camera_source = 0` line in the `camera_inspector.py` script to `1`, `2`, or `3` and re-running the script.
    ```python
    # Change this line in camera_inspector.py
    camera_source = 1 # Try 1, 2, etc.
    ```
*   **No window appears / Script crashes**: Ensure your OpenCV installation is correct. If you're using a virtual environment, ensure it's activated before installing libraries and running the script. Restarting your computer can sometimes help if the webcam is in use by another application.
