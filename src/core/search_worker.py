# =============================================================================
# search_worker.py — Background Search Thread & Timeline Exporter
# =============================================================================
#
# This file handles the search operation in a background thread so the UI
# doesn't freeze while scanning hundreds or thousands of frames.
#
# HOW SEARCH WORKS (for beginners):
#   1. User types a query like "red car with white stripe" and clicks Search
#   2. We fetch all frames from the database in the chosen time range
#   3. For each frame, we ask the AI: "does this match the query?"
#   4. Each match is emitted as a signal → shown in the UI as a result card
#   5. After all frames are checked, we emit the finished signal with total count
#
# If the AI fails multiple times in a row (network issues, quota exceeded),
# we automatically fall back to keyword matching on saved descriptions.
#
# TimelineExporter:
#   Takes a list of search results and exports them as a folder of images
#   sorted chronologically with a timeline.txt summary file.
#   It checks disk space first and handles errors gracefully.
# =============================================================================

import os
import shutil
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal
from core.storage import search_frames, get_setting, get_secure_setting
from core.ai_handler import search_with_ai, TEXT_ONLY_PROVIDERS, ENHANCE_PROVIDERS
from core.local_search import local_search, build_frame_description


class SearchWorker(QThread):
    result_found = pyqtSignal(dict)       # one result per match
    progress     = pyqtSignal(int, int)   # current, total
    finished     = pyqtSignal(int)        # total matches
    status       = pyqtSignal(str)        # status message
    error        = pyqtSignal(str)        # non-fatal error message

    def __init__(self, query: str, hours_back: float,
                 camera_ids=None, use_enhancement=False):
        super().__init__()
        self.query           = query
        self.hours_back      = hours_back
        self.camera_ids      = camera_ids
        self.use_enhancement = use_enhancement
        self.running         = True

    def run(self):
        self.status.emit("Fetching frames from database…")

        try:
            frames = search_frames(self.query, self.hours_back, self.camera_ids)
        except Exception as e:
            self.error.emit(f"Database error: {e}")
            self.finished.emit(0)
            return

        total = len(frames)
        if total == 0:
            self.status.emit("No frames found in the selected time range.")
            self.finished.emit(0)
            return

        provider    = get_setting("ai_provider", "")
        api_key     = get_secure_setting("ai_api_key", "")
        has_api     = bool(provider and api_key)
        is_deepseek = provider in TEXT_ONLY_PROVIDERS
        can_enhance = provider in ENHANCE_PROVIDERS and self.use_enhancement

        if not has_api:
            mode = "Local vision search (no API key — color/object detection)"
        elif is_deepseek:
            mode = "DeepSeek — keyword match (text only)"
        elif can_enhance:
            mode = f"AI vision + photo enhancement via {provider.upper()}"
        else:
            mode = f"AI vision search via {provider.upper()}"

        self.status.emit(f"Scanning {total} frame{'s' if total != 1 else ''}… ({mode})")
        matches         = 0
        consecutive_err = 0
        MAX_ERRORS      = 5

        for i, frame in enumerate(frames):
            if not self.running:
                break

            frame_id, camera_id, filepath, timestamp, existing_desc, cam_name = frame
            self.progress.emit(i + 1, total)

            # Update status every 20 frames so user sees progress
            if i % 20 == 0 and total > 20:
                pct = int((i / total) * 100)
                self.status.emit(f"Scanning… {pct}% ({i}/{total} frames, {matches} matches so far)")

            if not os.path.exists(filepath):
                continue

            if has_api:
                try:
                    matched, description = search_with_ai(
                        self.query, filepath,
                        saved_description=existing_desc,
                        use_enhancement=can_enhance
                    )
                    consecutive_err = 0
                except RuntimeError as e:
                    consecutive_err += 1
                    self.error.emit(str(e))
                    if consecutive_err >= MAX_ERRORS:
                        self.status.emit(
                            f"Too many AI errors ({consecutive_err}). "
                            "Switching to keyword fallback."
                        )
                        # Fall back to keyword matching for remaining frames
                        has_api = False
                    continue
            else:
                # No API configured — use local computer vision search
                # This works offline with no API key needed.
                # It's less accurate than AI but far better than nothing.
                matched, description = local_search(
                    self.query, filepath,
                    saved_description=existing_desc
                )

            if matched:
                matches += 1
                self.result_found.emit({
                    "frame_id":    frame_id,
                    "camera_id":   camera_id,
                    "camera_name": cam_name,
                    "filepath":    filepath,
                    "timestamp":   timestamp,
                    "description": description,
                    "query":       self.query,
                })

        cam_count = len(set(f[1] for f in frames))
        if matches == 0:
            self.status.emit(
                f"No matches found for '{self.query}' in the last "
                f"{int(self.hours_back)}h across {cam_count} camera(s). "
                f"Try different keywords or a longer time range."
            )
        else:
            self.status.emit(
                f"Search complete — {matches} match{'es' if matches != 1 else ''} "
                f"found across {cam_count} camera(s)"
            )
        self.finished.emit(matches)

    def stop(self):
        self.running = False


class TimelineExporter(QThread):
    """
    Takes a list of result dicts and exports them as:
    - Sorted copies of the matched frames
    - A timeline.txt summary
    - Checks disk space before writing
    """
    progress = pyqtSignal(int, int)
    finished = pyqtSignal(str)   # export path
    error    = pyqtSignal(str)

    def __init__(self, results: list, export_dir: str):
        super().__init__()
        self.results    = results
        self.export_dir = export_dir

    def run(self):
        try:
            # Check disk space
            needed  = sum(
                os.path.getsize(r["filepath"])
                for r in self.results
                if os.path.exists(r["filepath"])
            )
            free    = shutil.disk_usage(self.export_dir).free
            if free < needed + 50 * 1024 * 1024:  # need space + 50 MB buffer
                self.error.emit(
                    f"Not enough disk space. Need {needed // (1024*1024)} MB, "
                    f"only {free // (1024*1024)} MB available."
                )
                return

            # Sort by timestamp
            sorted_results = sorted(self.results, key=lambda r: r["timestamp"])
            total          = len(sorted_results)

            export_name = "Fovea_Timeline_" + datetime.now().strftime("%Y%m%d_%H%M%S")
            out_dir     = os.path.join(self.export_dir, export_name)
            os.makedirs(out_dir, exist_ok=True)

            timeline_lines = [
                "Fovea Timeline Export",
                f"Query: {sorted_results[0]['query'] if sorted_results else ''}",
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"Total matches: {total}",
                "=" * 60,
                ""
            ]

            for i, result in enumerate(sorted_results):
                self.progress.emit(i + 1, total)
                filepath  = result["filepath"]
                if not os.path.exists(filepath):
                    continue

                # Name: 001_CameraName_2026-03-19_14-22-05.jpg
                ext      = os.path.splitext(filepath)[1]
                ts_clean = result["timestamp"].replace(":", "-").replace(" ", "_")
                cam_safe = result["camera_name"].replace(" ", "_").replace("/", "_")
                new_name = f"{i+1:04d}_{cam_safe}_{ts_clean}{ext}"
                dest     = os.path.join(out_dir, new_name)
                shutil.copy2(filepath, dest)

                timeline_lines.append(
                    f"[{i+1:04d}] {result['timestamp']}  —  {result['camera_name']}"
                )
                if result.get("description"):
                    timeline_lines.append(f"       {result['description'][:120]}")
                timeline_lines.append("")

            # Write timeline text file
            tl_path = os.path.join(out_dir, "timeline.txt")
            with open(tl_path, "w", encoding="utf-8") as f:
                f.write("\n".join(timeline_lines))

            self.finished.emit(out_dir)

        except PermissionError as e:
            self.error.emit(f"Permission denied writing to that folder: {e}")
        except OSError as e:
            self.error.emit(f"Export failed: {e}")
        except Exception as e:
            self.error.emit(f"Unexpected export error: {e}")