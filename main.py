from pathlib import Path
import shutil
import subprocess
import threading
import uuid
import re
import sys
import time
import xml.sax.saxutils as xml_utils

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_DIR = Path(__file__).resolve().parent

# Your one-time Android template
TEMPLATE_DIR = PROJECT_DIR / "android_template"

# Temporary build projects
BUILDS_DIR = PROJECT_DIR / "builds"

# Generated APKs
OUTPUT_DIR = PROJECT_DIR / "output"


# How long abandoned jobs/files can remain on the server
CLEANUP_AFTER_SECONDS = 60 * 60  # 1 hour


# ============================================================
# CREATE REQUIRED DIRECTORIES
# ============================================================

BUILDS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="WebToAPK Generator",
    description="Generate Android APK from a website URL.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://web-to-apk-smoky.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# JOB STORAGE
# ============================================================

jobs = {}

jobs_lock = threading.Lock()


# ============================================================
# REQUEST MODEL
# ============================================================

class GenerateRequest(BaseModel):
    url: str
    app_name: str


# ============================================================
# SAFE APP NAME
# ============================================================

def make_safe_name(name: str) -> str:

    safe_name = "".join(
        c if c.isalnum() or c in "_-" else "_"
        for c in name
    )

    safe_name = safe_name.strip("_")

    if not safe_name:
        safe_name = "MyApp"

    return safe_name[:50]


# ============================================================
# VALIDATE URL
# ============================================================

def validate_url(url: str) -> str:

    url = url.strip()

    if not url:
        raise ValueError("Website URL cannot be empty.")

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Basic validation
    pattern = re.compile(
        r"^https?://"
        r"([a-zA-Z0-9-]+\.)+"
        r"[a-zA-Z]{2,}"
        r"([/?#].*)?$"
    )

    if not pattern.match(url):
        raise ValueError("Invalid website URL.")

    return url


# ============================================================
# CREATE BUILD PROJECT
# ============================================================

def create_build_project(
    app_name: str,
    job_id: str
) -> Path:

    safe_name = make_safe_name(app_name)

    build_dir = BUILDS_DIR / job_id / safe_name

    if build_dir.exists():
        shutil.rmtree(build_dir)

    build_dir.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    print("Copying Android template...")

    shutil.copytree(
        TEMPLATE_DIR,
        build_dir
    )

    print("Template copied successfully.")

    return build_dir


# ============================================================
# SET WEBSITE URL
# ============================================================

def set_website_url(
    build_dir: Path,
    website_url: str
):

    gradle_file = (
        build_dir
        / "app"
        / "build.gradle.kts"
    )

    if not gradle_file.exists():
        raise RuntimeError(
            "app/build.gradle.kts not found."
        )

    content = gradle_file.read_text(
        encoding="utf-8"
    )

    old_value = '"\\"https://example.com\\""'

    new_value = f'"\\\"{website_url}\\\""'

    if old_value not in content:

        raise RuntimeError(
            "WEBSITE_URL placeholder not found "
            "in build.gradle.kts."
        )

    content = content.replace(
        old_value,
        new_value
    )

    gradle_file.write_text(
        content,
        encoding="utf-8"
    )

    print(
        f"Website URL configured: {website_url}"
    )


# ============================================================
# SET APPLICATION NAME
# ============================================================

def set_app_name(
    build_dir: Path,
    app_name: str
):

    strings_file = (
        build_dir
        / "app"
        / "src"
        / "main"
        / "res"
        / "values"
        / "strings.xml"
    )

    if not strings_file.exists():
        raise RuntimeError(
            "strings.xml not found."
        )

    content = strings_file.read_text(
        encoding="utf-8"
    )

    escaped_name = xml_utils.escape(
        app_name
    )

    new_content, count = re.subn(
        r'(<string\s+name="app_name">).*?(</string>)',
        rf'\g<1>{escaped_name}\g<2>',
        content
    )

    if count == 0:
        raise RuntimeError(
            "app_name not found in strings.xml."
        )

    strings_file.write_text(
        new_content,
        encoding="utf-8"
    )

    print(
        f"App name configured: {app_name}"
    )


# ============================================================
# FIND GRADLE COMMAND
# ============================================================

def get_gradle_command(build_dir: Path):

    if sys.platform.startswith("win"):

        gradle_file = build_dir / "gradlew.bat"

        if not gradle_file.exists():
            raise RuntimeError(
                "gradlew.bat not found."
            )

        return [str(gradle_file)]

    else:

        gradle_file = build_dir / "gradlew"

        if not gradle_file.exists():
            raise RuntimeError(
                "gradlew not found."
            )

        # Make executable on Linux/macOS
        gradle_file.chmod(
            gradle_file.stat().st_mode | 0o111
        )

        return [str(gradle_file)]


# ============================================================
# BUILD APK
# ============================================================

def build_apk(
    build_dir: Path,
    app_name: str,
    job_id: str
):

    gradle_command = get_gradle_command(
        build_dir
    )

    command = gradle_command + [
        "assembleDebug"
    ]

    print()
    print("================================")
    print("Building Android APK...")
    print("================================")
    print()

    process = subprocess.Popen(
        command,
        cwd=build_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    logs = []

    # Read Gradle output
    for line in process.stdout:

        line = line.rstrip()

        if line:
            print(line)
            logs.append(line)

    return_code = process.wait()

    if return_code != 0:

        raise RuntimeError(
            "Gradle build failed.\n\n"
            + "\n".join(logs[-50:])
        )

    apk_file = (
        build_dir
        / "app"
        / "build"
        / "outputs"
        / "apk"
        / "debug"
        / "app-debug.apk"
    )

    if not apk_file.exists():

        raise RuntimeError(
            "Gradle completed but APK "
            "was not found."
        )

    safe_name = make_safe_name(
        app_name
    )

    output_dir = (
        OUTPUT_DIR / job_id
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_apk = (
        output_dir
        / f"{safe_name}.apk"
    )

    shutil.copy2(
        apk_file,
        output_apk
    )

    return output_apk


# ============================================================
# CLEAN BUILD DIRECTORY
# ============================================================

def delete_build_directory(
    job_id: str
):

    job_build_dir = (
        BUILDS_DIR / job_id
    )

    if job_build_dir.exists():

        shutil.rmtree(
            job_build_dir,
            ignore_errors=True
        )

        print(
            f"Deleted build directory: {job_id}"
        )


# ============================================================
# DELETE OUTPUT APK
# ============================================================

def delete_output_file(
    apk_path: Path,
    job_id: str
):

    try:

        if apk_path.exists():

            apk_path.unlink()

            print(
                f"Deleted APK: {apk_path}"
            )

        output_dir = (
            OUTPUT_DIR / job_id
        )

        if output_dir.exists():

            shutil.rmtree(
                output_dir,
                ignore_errors=True
            )

    finally:

        delete_build_directory(
            job_id
        )

        with jobs_lock:

            jobs.pop(
                job_id,
                None
            )


# ============================================================
# APK GENERATION WORKER
# ============================================================

def generate_apk_worker(
    job_id: str,
    website_url: str,
    app_name: str
):

    build_dir = None

    try:

        with jobs_lock:

            jobs[job_id]["status"] = "building"
            jobs[job_id]["message"] = (
                "Creating Android project..."
            )

        # ----------------------------------------------------
        # Copy template
        # ----------------------------------------------------

        build_dir = create_build_project(
            app_name,
            job_id
        )

        # ----------------------------------------------------
        # Configure URL
        # ----------------------------------------------------

        with jobs_lock:

            jobs[job_id]["message"] = (
                "Configuring website URL..."
            )

        set_website_url(
            build_dir,
            website_url
        )

        # ----------------------------------------------------
        # Configure app name
        # ----------------------------------------------------

        with jobs_lock:

            jobs[job_id]["message"] = (
                "Configuring app name..."
            )

        set_app_name(
            build_dir,
            app_name
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Logo is NOT changed here.
        #
        # The logo already exists inside your
        # Android template.
        # ----------------------------------------------------

        with jobs_lock:

            jobs[job_id]["message"] = (
                "Building APK..."
            )

        # ----------------------------------------------------
        # Build APK
        # ----------------------------------------------------

        apk_path = build_apk(
            build_dir,
            app_name,
            job_id
        )

        # ----------------------------------------------------
        # Finished
        # ----------------------------------------------------

        with jobs_lock:

            jobs[job_id]["status"] = "completed"

            jobs[job_id]["message"] = (
                "APK generated successfully."
            )

            jobs[job_id]["apk_path"] = str(
                apk_path
            )

            jobs[job_id]["download_name"] = (
                apk_path.name
            )

            jobs[job_id]["completed_at"] = (
                time.time()
            )

        print()
        print("================================")
        print("APK GENERATED SUCCESSFULLY!")
        print("================================")
        print(apk_path)
        print("================================")

    except Exception as error:

        print()
        print("BUILD ERROR:")
        print(error)

        with jobs_lock:

            jobs[job_id]["status"] = "failed"

            jobs[job_id]["message"] = str(
                error
            )

            jobs[job_id]["completed_at"] = (
                time.time()
            )

        # Clean build folder if generation failed
        delete_build_directory(
            job_id
        )


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return {
        "name": "WebToAPK Generator",
        "status": "running",
        "message": "Backend is working."
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok"
    }


# ============================================================
# GENERATE APK
# ============================================================

@app.post("/generate")
def generate(
    request: GenerateRequest
):

    # --------------------------------------------------------
    # Validate URL
    # --------------------------------------------------------

    try:

        website_url = validate_url(
            request.url
        )

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    # --------------------------------------------------------
    # Validate app name
    # --------------------------------------------------------

    app_name = request.app_name.strip()

    if not app_name:

        raise HTTPException(
            status_code=400,
            detail="App name cannot be empty."
        )

    if len(app_name) > 50:

        raise HTTPException(
            status_code=400,
            detail="App name is too long."
        )

    # --------------------------------------------------------
    # Check template
    # --------------------------------------------------------

    if not TEMPLATE_DIR.exists():

        raise HTTPException(
            status_code=500,
            detail="Android template not found."
        )

    # --------------------------------------------------------
    # Generate unique job ID
    # --------------------------------------------------------

    job_id = uuid.uuid4().hex

    # --------------------------------------------------------
    # Create job
    # --------------------------------------------------------

    with jobs_lock:

        jobs[job_id] = {

            "status": "queued",

            "message": (
                "APK generation queued."
            ),

            "url": website_url,

            "app_name": app_name,

            "apk_path": None,

            "download_name": None,

            "created_at": time.time(),

            "completed_at": None
        }

    # --------------------------------------------------------
    # Start build in background thread
    # --------------------------------------------------------

    thread = threading.Thread(
        target=generate_apk_worker,
        args=(
            job_id,
            website_url,
            app_name
        ),
        daemon=True
    )

    thread.start()

    # --------------------------------------------------------
    # Return job ID immediately
    # --------------------------------------------------------

    return {

        "success": True,

        "job_id": job_id,

        "status": "queued",

        "message": (
            "APK generation started."
        )
    }


# ============================================================
# CHECK GENERATION STATUS
# ============================================================

@app.get("/status/{job_id}")
def get_status(
    job_id: str
):

    with jobs_lock:

        job = jobs.get(job_id)

        if not job:

            raise HTTPException(
                status_code=404,
                detail="Job not found."
            )

        response = {
            "job_id": job_id,
            "status": job["status"],
            "message": job["message"]
        }

        if job["status"] == "completed":

            response["download_url"] = (
                f"/download/{job_id}"
            )

            response["file_name"] = (
                job["download_name"]
            )

        if job["status"] == "failed":

            response["error"] = (
                job["message"]
            )

        return response


# ============================================================
# DOWNLOAD APK
# ============================================================

@app.get("/download/{job_id}")
def download_apk(
    job_id: str,
    background_tasks: BackgroundTasks
):

    with jobs_lock:

        job = jobs.get(job_id)

        if not job:

            raise HTTPException(
                status_code=404,
                detail="Job not found."
            )

        if job["status"] != "completed":

            raise HTTPException(
                status_code=400,
                detail="APK is not ready."
            )

        apk_path = Path(
            job["apk_path"]
        )

        download_name = job[
            "download_name"
        ]

    # --------------------------------------------------------
    # Security check
    # --------------------------------------------------------

    try:

        apk_path.resolve().relative_to(
            OUTPUT_DIR.resolve()
        )

    except ValueError:

        raise HTTPException(
            status_code=403,
            detail="Invalid APK path."
        )

    if not apk_path.exists():

        raise HTTPException(
            status_code=404,
            detail="APK file no longer exists."
        )

    # --------------------------------------------------------
    # Delete AFTER response has been sent
    # --------------------------------------------------------

    background_tasks.add_task(
        delete_output_file,
        apk_path,
        job_id
    )

    return FileResponse(
        path=apk_path,
        filename=download_name,
        media_type=(
            "application/vnd.android.package-archive"
        )
    )


# ============================================================
# CLEANUP OLD JOBS
# ============================================================

def cleanup_old_jobs():

    current_time = time.time()

    jobs_to_delete = []

    with jobs_lock:

        for job_id, job in jobs.items():

            created_at = job[
                "created_at"
            ]

            age = (
                current_time - created_at
            )

            if age > CLEANUP_AFTER_SECONDS:

                jobs_to_delete.append(
                    job_id
                )

    for job_id in jobs_to_delete:

        print(
            f"Cleaning old job: {job_id}"
        )

        with jobs_lock:

            job = jobs.pop(
                job_id,
                None
            )

        if job:

            apk_path = job.get(
                "apk_path"
            )

            if apk_path:

                path = Path(apk_path)

                if path.exists():

                    path.unlink(
                        missing_ok=True
                    )

        delete_build_directory(
            job_id
        )


# ============================================================
# STARTUP CLEANUP
# ============================================================

@app.on_event("startup")
def startup():

    print()
    print("================================")
    print("       WebToAPK Generator")
    print("================================")
    print()
    print("Template:", TEMPLATE_DIR)
    print("Builds  :", BUILDS_DIR)
    print("Output  :", OUTPUT_DIR)
    print()
    print("Server is ready.")
    print()
