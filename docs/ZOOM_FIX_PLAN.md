# Fix Plan: YouTube Demo Zoom Issue

**Issue**: The demo video stream appears "zoomed in", likely due to `yt-dlp` selecting a cropped or non-standard stream when restricted to `height<=720`, or displaying at an odd resolution (1288x880).

**Diagnosis**:
*   Current Code: `ydl_opts = {'format': 'best[height<=720]'}`.
*   Risk: If YouTube offers a specialized 720p stream (e.g., for mobile) that is cropped, this selector picks it.
*   Goal: Ensure **Full Field of View** (FOV) while keeping file size manageable.

**Proposed Solution**:
1.  **Modify `yt-dlp` selector**: Change from `best[height<=720]` to `best` (highest quality available). This guarantees the full source FOV.
2.  **Modify `ffmpeg` filter**: Add a scale filter to the `-vf` chain: `scale=-1:720`.
    *   This forces the *full* high-res stream to be resized to 720p height (maintaining aspect ratio) *before* processing.
    *   Result: A standard ~1280x720 image with the full wide-angle view, solving the zoom issue.

**Implementation Steps**:
1.  Edit `IntelliOptics 2.0/cloud/backend/app/services/youtube_capture.py`.
2.  Update `ydl_opts` to `{'format': 'best'}`.
3.  Update `ffmpeg_cmd` to include `scale=-1:720` in the filter graph.
4.  Restart the backend container.
