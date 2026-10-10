# ============================================================
# AGNES VIDEO GENERATION - QUEUE / STATUS ERROR FIX
# ============================================================

def call_agnes_video(
    prompt,
    quality="720p",
    ratio="16:9",
    num_frames=241,
    duration=10,
    reference_image=None,
    audio_prompt=None,
    max_minutes=12
):
    key = get_api_key()

    if not key:
        return {
            "success": False,
            "error": "Agnes API key is missing."
        }

    model = APIS["agnes"]["models"]["video"]

    final_prompt = prompt.strip()
    if audio_prompt:
        final_prompt += f"\nAudio and dialogue: {audio_prompt.strip()}"

    payload = {
        "model": model,
        "prompt": final_prompt,
        "size": "720P",
        "seconds": str(duration),
        "mode": "text"
    }

    if reference_image is not None:
        try:
            reference_image.seek(0)
            image_bytes = reference_image.read()

            if not image_bytes:
                return {
                    "success": False,
                    "error": "The reference image is empty."
                }

            payload["image"] = base64.b64encode(
                image_bytes
            ).decode("utf-8")

            payload["mode"] = "reference"

        except Exception as exc:
            return {
                "success": False,
                "error": f"Reference image error: {exc}"
            }

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

    # Video creation endpoint
    start_url = f"{APIS['agnes']['base_url']}/videos"

    # Status endpoint is separate from the /v1 API path.
    status_url = "https://apihub.agnes-ai.com/agnesapi"

    try:
        st.info("Submitting video generation request...")

        response = requests.post(
            start_url,
            headers=headers,
            json=payload,
            timeout=(20, 90)
        )

        if response.status_code == 429:
            return {
                "success": False,
                "error": (
                    "Agnes returned HTTP 429 (rate limit or queue limit). "
                    "Wait before retrying. API response: "
                    + extract_error(response)
                )
            }

        if response.status_code not in (200, 201, 202):
            return {
                "success": False,
                "error": (
                    f"Video creation failed (HTTP "
                    f"{response.status_code}): "
                    f"{extract_error(response)}"
                )
            }

        try:
            data = response.json()
        except ValueError:
            return {
                "success": False,
                "error": (
                    "Agnes returned a non-JSON response when "
                    "starting the video job: "
                    + response.text[:1000]
                )
            }

        # Accommodate common response wrappers.
        job_data = data
        if isinstance(data.get("data"), dict):
            job_data = data["data"]
        elif isinstance(data.get("result"), dict):
            job_data = data["result"]

        video_id = (
            job_data.get("video_id")
            or job_data.get("id")
            or job_data.get("job_id")
            or data.get("video_id")
            or data.get("id")
            or data.get("job_id")
        )

        if not video_id:
            return {
                "success": False,
                "error": (
                    "Agnes accepted the request but returned no "
                    "recognizable video/job ID. Response: "
                    + str(data)[:1500]
                )
            }

        st.success(f"Video job submitted: {video_id}")

    except requests.RequestException as exc:
        return {
            "success": False,
            "error": f"Video submission network error: {exc}"
        }
    except Exception as exc:
        return {
            "success": False,
            "error": f"Video submission error: {exc}"
        }

    progress_bar = st.progress(0)
    status_text = st.empty()

    started_at = time.time()
    poll_count = 0
    last_http_error = None

    failed_statuses = {
        "failed", "failure", "cancelled", "canceled",
        "error", "expired", "rejected"
    }

    completed_statuses = {
        "completed", "complete", "success", "succeeded",
        "finished", "done"
    }

    while True:
        elapsed = time.time() - started_at

        if elapsed >= max_minutes * 60:
            progress_bar.empty()
            status_text.empty()

            return {
                "success": False,
                "error": (
                    f"Video status was not completed within "
                    f"{max_minutes} minutes. "
                    f"Job ID: {video_id}. "
                    f"Last HTTP error: {last_http_error or 'None'}"
                ),
                "video_id": video_id
            }

        if poll_count < 5:
            interval = 3
        elif poll_count < 15:
            interval = 5
        else:
            interval = 8

        time.sleep(interval)
        poll_count += 1

        try:
            # IMPORTANT: use the status endpoint with query parameters.
            status_response = requests.get(
                status_url,
                headers={
                    "Authorization": f"Bearer {key}"
                },
                params={
                    "video_id": str(video_id),
                    "model_name": model
                },
                timeout=(15, 30)
            )

        except requests.RequestException as exc:
            last_http_error = str(exc)
            status_text.warning(
                f"Temporary status connection error. "
                f"Retrying... ({poll_count})"
            )
            continue

        if status_response.status_code != 200:
            last_http_error = (
                f"HTTP {status_response.status_code}: "
                f"{extract_error(status_response)}"
            )

            # Authentication and invalid endpoint errors will not
            # normally be resolved by repeatedly polling.
            if status_response.status_code in (400, 401, 403, 404):
                progress_bar.empty()
                status_text.empty()

                return {
                    "success": False,
                    "error": (
                        "Video status check failed: "
                        + last_http_error
                        + f". Job ID: {video_id}"
                    ),
                    "video_id": video_id
                }

            status_text.warning(
                f"Status check returned {last_http_error}. "
                "Retrying..."
            )
            continue

        try:
            status_data = status_response.json()
        except ValueError:
            last_http_error = (
                "Status endpoint returned invalid JSON: "
                + status_response.text[:500]
            )
            status_text.warning(
                "Invalid status response. Retrying..."
            )
            continue

        if not isinstance(status_data, dict):
            last_http_error = (
                "Unexpected status response: "
                + str(status_data)[:500]
            )
            continue

        # Support common response wrappers.
        result_data = status_data

        if isinstance(status_data.get("data"), dict):
            result_data = status_data["data"]
        elif isinstance(status_data.get("result"), dict):
            result_data = status_data["result"]

        api_error = (
            result_data.get("error")
            or status_data.get("error")
        )

        if api_error:
            if isinstance(api_error, dict):
                error_text = (
                    api_error.get("message")
                    or api_error.get("detail")
                    or str(api_error)
                )
            else:
                error_text = str(api_error)

            progress_bar.empty()
            status_text.empty()

            return {
                "success": False,
                "error": f"Agnes video error: {error_text}",
                "video_id": video_id
            }

        internal_status = str(
            result_data.get("internal_status", "")
        ).lower()

        external_status = str(
            result_data.get("status", "")
        ).lower()

        task_status = str(
            result_data.get("task_status", "")
        ).lower()

        job_status = (
            internal_status
            or external_status
            or task_status
        )

        if job_status in failed_statuses:
            progress_bar.empty()
            status_text.empty()

            return {
                "success": False,
                "error": (
                    f"Agnes job status: {job_status}. "
                    f"Response: {str(result_data)[:1200]}"
                ),
                "video_id": video_id
            }

        # Find a video URL in common response formats.
        video_url = (
            result_data.get("url")
            or result_data.get("video_url")
        )

        for field in ("metadata", "video", "output", "data"):
            obj = result_data.get(field)
            if isinstance(obj, dict):
                video_url = (
                    video_url
                    or obj.get("url")
                    or obj.get("video_url")
                    or obj.get("videoUrl")
                )

        if not video_url:
            for field in ("metadata", "video", "output"):
                obj = status_data.get(field)
                if isinstance(obj, dict):
                    video_url = (
                        obj.get("url")
                        or obj.get("video_url")
                        or obj.get("videoUrl")
                    )
                    if video_url:
                        break

        # Some APIs return the URL only after a completed status.
        if video_url:
            progress_bar.progress(100)
            status_text.success(
                "Video is ready. Downloading..."
            )

            download_result = download_url_to_file(
                video_url,
                headers={"Authorization": f"Bearer {key}"}
            )

            progress_bar.empty()
            status_text.empty()

            if download_result.get("success"):
                return {
                    "success": True,
                    "path": download_result["path"],
                    "url": video_url,
                    "api": "Agnes AI 2.5-flash",
                    "video_id": video_id
                }

            # The URL may still be playable even if server download
            # fails, so return it with a visible warning.
            return {
                "success": True,
                "url": video_url,
                "api": "Agnes AI 2.5-flash",
                "video_id": video_id,
                "download_warning": download_result.get(
                    "error", "Server download failed."
                )
            }

        if job_status in completed_statuses:
            progress_bar.empty()
            status_text.empty()

            return {
                "success": False,
                "error": (
                    "Agnes reports that the job is complete, "
                    "but no video URL was found in its response. "
                    f"Response: {str(status_data)[:1500]}"
                ),
                "video_id": video_id
            }

        # Keep progress below 100% until a real video URL appears.
        progress = min(
            95,
            int(95 * elapsed / max(1, max_minutes * 60))
        )

        progress_bar.progress(progress)

        status_text.text(
            f"Generating video... {progress}% · "
            f"{int(elapsed // 60)}m "
            f"{int(elapsed % 60)}s · "
            f"Status: {job_status or 'processing'}"
        )
