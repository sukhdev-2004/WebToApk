import { useEffect, useRef, useState } from "react";
import "./App.css";

const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

const STATUS_PROGRESS = {
  starting: 4,
  queued: 12,
  building: 64,
  completed: 100,
  failed: 0,
};

const STATUS_LABELS = {
  starting: "Connecting to builder",
  queued: "Build queued",
  building: "Android project is compiling",
  completed: "APK ready to install",
  failed: "Build stopped",
};

const STAGES = [
  { label: "Prepare", threshold: 10 },
  { label: "Configure", threshold: 35 },
  { label: "Compile", threshold: 55 },
  { label: "Package", threshold: 90 },
];

function App() {
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [appName, setAppName] = useState("");

  const [status, setStatus] = useState("idle");
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState([]);

  const [downloadUrl, setDownloadUrl] = useState("");
  const [error, setError] = useState("");

  const [loading, setLoading] = useState(false);

  const logContainerRef = useRef(null);
  const pollTimerRef = useRef(null);

  // Automatically scroll build console to the latest log
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop =
        logContainerRef.current.scrollHeight;
    }
  }, [logs]);

  useEffect(() => () => clearTimeout(pollTimerRef.current), []);

  const addLog = (text) => {
    if (!text) return;

    setLogs((previous) => {
      const newLines = String(text)
        .split("\n")
        .map((line) => line.trimEnd())
        .filter((line) => line.length > 0);

      return [...previous, ...newLines];
    });
  };

  const scheduleStatusCheck = (jobId) => {
    clearTimeout(pollTimerRef.current);
    pollTimerRef.current = setTimeout(() => checkStatus(jobId), 1500);
  };

  const handleGenerate = async () => {
    setError("");
    setDownloadUrl("");
    setLogs([]);
    setProgress(0);
    setStatus("starting");

    if (!websiteUrl.trim()) {
      setError("Please enter a website URL.");
      setStatus("idle");
      return;
    }

    if (!appName.trim()) {
      setError("Please enter an app name.");
      setStatus("idle");
      return;
    }

    try {
      setLoading(true);

      addLog("Starting APK generation...");
      addLog("Preparing Android project...");

      const response = await fetch(`${API_URL}/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          url: websiteUrl.trim(),
          app_name: appName.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to start APK generation."
        );
      }

      if (!data.job_id) {
        throw new Error("Server did not return a job ID.");
      }

      addLog(`Job created: ${data.job_id}`);
      addLog("Waiting for Android build to start...");

      setStatus("queued");

      checkStatus(data.job_id);
    } catch (err) {
      console.error(err);

      setStatus("failed");
      setError(err.message || "Something went wrong.");
      setLoading(false);
    }
  };

  const checkStatus = async (jobId) => {
    try {
      const response = await fetch(`${API_URL}/status/${jobId}`);

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Unable to check build status."
        );
      }

      console.log("Build status:", data);

      const nextProgress = typeof data.progress === "number"
        ? Math.min(100, Math.max(0, data.progress))
        : STATUS_PROGRESS[data.status] ?? progress;
      setProgress(nextProgress);

      if (data.message && data.message !== logs[logs.length - 1]) {
        addLog(data.message);
      }

      // Support backend logs
      if (data.logs) {
        if (Array.isArray(data.logs)) {
          setLogs(data.logs);
        } else {
          setLogs(
            String(data.logs)
              .split("\n")
              .filter((line) => line.trim() !== "")
          );
        }
      }

      if (data.status === "queued") {
        setStatus("queued");
        scheduleStatusCheck(jobId);
        return;
      }

      if (data.status === "building") {
        setStatus("building");
        scheduleStatusCheck(jobId);
        return;
      }

      if (data.status === "completed") {
        setStatus("completed");
        setProgress(100);

        addLog("");
        addLog("BUILD SUCCESSFUL");
        addLog("APK generation completed successfully.");

        if (data.download_url) {
          setDownloadUrl(`${API_URL}${data.download_url}`);
        }

        setLoading(false);

        return;
      }

      if (data.status === "failed") {
        setStatus("failed");

        if (data.error) {
          setError(data.error);
          addLog(`ERROR: ${data.error}`);
        } else {
          setError("APK build failed.");
          addLog("ERROR: APK build failed.");
        }

        setLoading(false);

        return;
      }

      // Unknown status
      scheduleStatusCheck(jobId);
    } catch (err) {
      console.error(err);

      setStatus("failed");
      setError(err.message || "Unable to communicate with server.");
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!downloadUrl) return;

    // Start download
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = `${appName || "app"}.apk`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    // Refresh after download has had time to start
    setTimeout(() => {
      window.location.reload();
    }, 1200);
  };

  const resetForm = () => {
    clearTimeout(pollTimerRef.current);
    setWebsiteUrl("");
    setAppName("");
    setStatus("idle");
    setProgress(0);
    setLogs([]);
    setDownloadUrl("");
    setError("");
    setLoading(false);
  };

  const getStatusText = () => {
    return STATUS_LABELS[status] || "Ready to build";
  };

  const isBuilding =
    status === "starting" ||
    status === "queued" ||
    status === "building";

  return (
    <div className="app">
      <div className="ambient ambient-top"></div>
      <div className="ambient ambient-bottom"></div>

      <main className="container">

        <section className="hero">
          <div className="eyebrow"><span className="eyebrow-dot"></span> Web to Android studio</div>
          <div className="hero-title-row">
            <div className="brand-icon"><span>W</span></div>
            <div>
              <p className="kicker">SHIP YOUR SITE</p>
              <h1>Website to <em>APK</em></h1>
            </div>
          </div>
          <p>
            Wrap any responsive website in a polished Android app, compiled and ready for your device.
          </p>
        </section>

        <section className="card">
          <div className="form-section">
            <div className="form-heading">
              <div><span className="section-number">01</span><span>Project details</span></div>
              <span className="secure-note">LOCAL BUILD <span className="status-dot"></span></span>
            </div>
            <div className="form-grid">
              <div className="form-group">
                <label htmlFor="website">Website URL</label>
              <div className="input-wrapper">
                <span className="input-icon">↗</span>

                <input
                  id="website"
                  type="url"
                  placeholder="https://example.com"
                  value={websiteUrl}
                  onChange={(e) => setWebsiteUrl(e.target.value)}
                  disabled={loading}
                />
              </div>
              </div>
              <div className="form-group">
                <label htmlFor="appName">Application name</label>
              <div className="input-wrapper">
                <span className="input-icon">✦</span>

                <input
                  id="appName"
                  type="text"
                  placeholder="My App Name"
                  value={appName}
                  onChange={(e) => setAppName(e.target.value)}
                  disabled={loading}
                />
              </div>
              </div>
            </div>

            {error && (
              <div className="error-box">
                <span>⚠️</span>
                <p>{error}</p>
              </div>
            )}

            <button
              className="generate-button"
              onClick={handleGenerate}
              disabled={loading}
            >
              {isBuilding ? (
                <>
                  <span className="button-spinner"></span>
                  Building your APK
                </>
              ) : (
                <>
                  Generate APK <span className="button-arrow">→</span>
                </>
              )}
            </button>

          </div>

          {(isBuilding || status === "completed" || status === "failed") && (
            <div className="build-section">
              <div className="build-header">
                <div>
                  <span className="section-number">02 / BUILD MONITOR</span>
                  <h2>{getStatusText()}</h2>
                  <p>{status === "completed" ? "Your application is ready." : status === "failed" ? "Something went wrong during the build." : "Your project is moving through the Android pipeline."}</p>
                </div>
                <div className="percentage"><strong>{progress}</strong><span>%</span></div>
              </div>

              {/* Progress bar */}
              <div className="progress-container">
                <div
                  className="progress-bar"
                  style={{ width: `${progress}%` }}
                ></div>
              </div>

              <div className="build-stages">
                {STAGES.map((stage) => <div className={progress >= stage.threshold ? "stage active" : "stage"} key={stage.label}><span>{progress >= stage.threshold ? "✓" : "○"}</span>{stage.label}</div>)}
              </div>

              {/* Console */}
              <div className="console-wrapper">

                <div className="console-header">
                  <div className="terminal-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>

                  <span>BUILD OUTPUT</span>

                  {isBuilding && (
                    <span className="live-indicator">
                      LIVE · POLLING
                    </span>
                  )}
                </div>

                <div
                  className="console"
                  ref={logContainerRef}
                >
                  {logs.length === 0 ? (
                    <div className="console-empty">
                      Waiting for build output...
                    </div>
                  ) : (
                    logs.map((log, index) => (
                      <div
                        className={
                          log.includes("ERROR")
                            ? "console-line error-line"
                            : log.includes("SUCCESS")
                              ? "console-line success-line"
                              : "console-line"
                        }
                        key={`${index}-${log}`}
                      >
                        <span className="console-prefix">{String(index + 1).padStart(2, "0")}</span>
                        {log}
                      </div>
                    ))
                  )}

                  {isBuilding && (
                    <div className="console-cursor">
                      <span>▊</span>
                    </div>
                  )}
                </div>

              </div>

              {/* Download */}
              {status === "completed" && downloadUrl && (
                <div className="success-section">

                  <div className="success-icon">
                    ✓
                  </div>

                  <h2>APK Generated Successfully!</h2>

                  <p>
                    Your Android application is ready to download.
                  </p>

                  <button
                    className="download-button"
                    onClick={handleDownload}
                  >
                    Download APK <span className="button-arrow">↓</span>
                  </button>

                  <small>
                    The generated files will be removed from the server
                    after download.
                  </small>

                </div>
              )}

              {/* Failed */}
              {status === "failed" && (
                <div className="failed-section">

                  <div className="failed-icon">
                    ✕
                  </div>

                  <h2>Build Failed</h2>

                  <p>
                    Please check the build output above.
                  </p>

                  <button
                    className="retry-button"
                    onClick={resetForm}
                  >
                    Try Again <span className="button-arrow">↻</span>
                  </button>

                </div>
              )}

            </div>
          )}

        </section>

        <footer>
          <div className="feature">
            <span className="feature-icon">01</span>
            <div>
              <strong>Automatic Build</strong>
              <small>Android project configured automatically</small>
            </div>
          </div>

          <div className="feature">
            <span className="feature-icon">02</span>
            <div>
              <strong>Temporary Files</strong>
              <small>Build files are automatically cleaned</small>
            </div>
          </div>

          <div className="feature">
            <span className="feature-icon">03</span>
            <div>
              <strong>Ready to Install</strong>
              <small>Download your generated APK</small>
            </div>
          </div>

        </footer>

      </main>
    </div>
  );
}

export default App;
