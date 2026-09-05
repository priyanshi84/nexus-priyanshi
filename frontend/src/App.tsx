import { useEffect, useState } from "react";

const API = "http://127.0.0.1:8000";

type Job = {
  id: string;
  type: string;
  body: string;
  status: string;
  attempts: number;
  created_at: string;
  updated_at: string;
};

type EventItem = {
  id: number;
  job_id: string | null;
  event_type: string;
  reason: string | null;
  created_at: string;
};

type Release = {
  id: number;
  version: string;
  status: string;
  description: string;
  created_at: string;
};

function App() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [releases, setReleases] = useState<Release[]>([]);
  const [failMode, setFailMode] = useState(false);
  const [workerRunning, setWorkerRunning] = useState(true);
  const [restartCount, setRestartCount] = useState(0);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  async function loadData() {
    try {
      const jobsResponse = await fetch(API + "/jobs/");
      const eventsResponse = await fetch(API + "/jobs/events");
      const releasesResponse = await fetch(API + "/releases/");
      const failureResponse = await fetch(API + "/failures/status");

      const jobsData = await jobsResponse.json();
      const eventsData = await eventsResponse.json();
      const releasesData = await releasesResponse.json();
      const failureData = await failureResponse.json();

      setJobs(jobsData.jobs || []);
      setEvents(eventsData.events || []);
      setReleases(releasesData.releases || []);
      setFailMode(failureData.fail_mode);
      setWorkerRunning(failureData.worker_running);
      setRestartCount(failureData.worker_restart_count || 0);

      setLoading(false);
    } catch (error) {
      console.error(error);
      setMessage("Backend is not reachable. Make sure FastAPI is running.");
      setLoading(false);
    }
  }

  useEffect(function () {
    loadData();

    const timer = setInterval(function () {
      loadData();
    }, 2000);

    return function () {
      clearInterval(timer);
    };
  }, []);

  async function enableFailure() {
    try {
      await fetch(API + "/failures/enable", {
        method: "POST",
      });

      setMessage("Failure mode enabled.");
      loadData();
    } catch {
      setMessage("Could not enable failure mode.");
    }
  }

  async function disableFailure() {
    try {
      await fetch(API + "/failures/disable", {
        method: "POST",
      });

      setMessage("Failure mode disabled.");
      loadData();
    } catch {
      setMessage("Could not disable failure mode.");
    }
  }

  async function stopWorker() {
    try {
      await fetch(API + "/failures/worker/stop", {
        method: "POST",
      });

      setMessage("Worker stopped.");
      loadData();
    } catch {
      setMessage("Could not stop worker.");
    }
  }

  async function startWorker() {
    try {
      await fetch(API + "/failures/worker/start", {
        method: "POST",
      });

      setMessage("Worker started.");
      loadData();
    } catch {
      setMessage("Could not start worker.");
    }
  }

  async function rollback() {
    try {
      const response = await fetch(API + "/releases/rollback", {
        method: "POST",
      });

      const data = await response.json();

      if (!response.ok) {
        setMessage(data.detail || "Rollback failed.");
        return;
      }

      setMessage(
        "Rollback successful: " +
          data.rolled_back +
          " -> " +
          data.restored
      );

      loadData();
    } catch {
      setMessage("Could not perform rollback.");
    }
  }

  const totalJobs = jobs.length;

  const successfulJobs = jobs.filter(function (job) {
    return job.status === "SUCCESS";
  }).length;

  const deadJobs = jobs.filter(function (job) {
    return job.status === "DEAD";
  }).length;

  const queuedJobs = jobs.filter(function (job) {
    return job.status === "QUEUED";
  }).length;

  const runningJobs = jobs.filter(function (job) {
    return job.status === "RUNNING";
  }).length;

  const retryJobs = jobs.filter(function (job) {
    return job.status === "RETRY_WAIT";
  }).length;

  const activeJobs = queuedJobs + runningJobs + retryJobs;

  const activeRelease = releases.find(function (release) {
    return release.status === "ACTIVE";
  });

  const oldestActiveJob = jobs
    .filter(function (job) {
      return (
        job.status === "QUEUED" ||
        job.status === "RUNNING" ||
        job.status === "RETRY_WAIT"
      );
    })
    .sort(function (a, b) {
      return (
        new Date(a.created_at).getTime() -
        new Date(b.created_at).getTime()
      );
    })[0];

  function getStatusClass(status: string) {
    if (status === "SUCCESS") {
      return "status success";
    }

    if (status === "DEAD") {
      return "status dead";
    }

    if (status === "RUNNING") {
      return "status running";
    }

    if (status === "RETRY_WAIT") {
      return "status retry";
    }

    return "status queued";
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-3xl font-bold">NEXUS</h1>
          <p className="text-slate-400 mt-2">
            Loading operator console...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">

      <header className="border-b border-slate-800 bg-slate-950">
        <div className="max-w-7xl mx-auto px-6 py-5 flex justify-between items-center">

          <div>
            <div className="flex items-center gap-3">

              <div
                className={
                  workerRunning
                    ? "w-3 h-3 rounded-full bg-emerald-400"
                    : "w-3 h-3 rounded-full bg-red-400"
                }
              />

              <h1 className="text-2xl font-bold">
                NEXUS
              </h1>

            </div>

            <p className="text-sm text-slate-400 mt-1">
              Infrastructure Engineering · Operator Console
            </p>
          </div>

          <div className="flex gap-3">

            <div
              className={
                workerRunning
                  ? "px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-sm"
                  : "px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm"
              }
            >
              Worker {workerRunning ? "Running" : "Stopped"}
            </div>

            <div className="px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-sm text-slate-400">
              Local Mode
            </div>

          </div>

        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-8">

        {message && (
          <div className="mb-6 px-5 py-4 rounded-xl bg-slate-900 border border-slate-700 text-sm text-slate-300">
            {message}
          </div>
        )}

        <div className="flex justify-between items-end mb-4">

          <div>
            <h2 className="text-xl font-semibold">
              System Overview
            </h2>

            <p className="text-sm text-slate-500 mt-1">
              Current operational state
            </p>
          </div>

          <button
            onClick={loadData}
            className="px-4 py-2 rounded-lg bg-slate-800 border border-slate-700 hover:bg-slate-700"
          >
            Refresh
          </button>

        </div>

        <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
            <p className="text-sm text-slate-400">
              Total Jobs
            </p>

            <p className="text-3xl font-bold mt-2">
              {totalJobs}
            </p>
          </div>

          <div className="rounded-xl border border-emerald-900 bg-emerald-950/20 p-5">
            <p className="text-sm text-emerald-300">
              Successful
            </p>

            <p className="text-3xl font-bold mt-2 text-emerald-400">
              {successfulJobs}
            </p>
          </div>

          <div className="rounded-xl border border-blue-900 bg-blue-950/20 p-5">
            <p className="text-sm text-blue-300">
              Active / Pending
            </p>

            <p className="text-3xl font-bold mt-2 text-blue-400">
              {activeJobs}
            </p>
          </div>

          <div className="rounded-xl border border-red-900 bg-red-950/20 p-5">
            <p className="text-sm text-red-300">
              Dead / Given Up
            </p>

            <p className="text-3xl font-bold mt-2 text-red-400">
              {deadJobs}
            </p>
          </div>

          <div className="rounded-xl border border-purple-900 bg-purple-950/20 p-5">
            <p className="text-sm text-purple-300">
              Worker Restarts
            </p>

            <p className="text-3xl font-bold mt-2 text-purple-400">
              {restartCount}
            </p>
          </div>

        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900 p-6 mb-8">

          <div className="flex justify-between items-start mb-6">

            <div>
              <h2 className="text-lg font-semibold">
                Backlog / Queue Health
              </h2>

              <p className="text-sm text-slate-400 mt-1">
                Current work pressure and processing state
              </p>
            </div>

            <div
              className={
                activeJobs === 0
                  ? "px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30"
                  : "px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/30"
              }
            >
              {activeJobs === 0 ? "HEALTHY" : "WORK IN QUEUE"}
            </div>

          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">

            <div className="rounded-lg bg-slate-950 border border-slate-800 p-4">
              <p className="text-xs text-slate-500">
                Queued
              </p>

              <p className="text-2xl font-bold mt-1">
                {queuedJobs}
              </p>
            </div>

            <div className="rounded-lg bg-slate-950 border border-slate-800 p-4">
              <p className="text-xs text-slate-500">
                Running
              </p>

              <p className="text-2xl font-bold mt-1 text-blue-400">
                {runningJobs}
              </p>
            </div>

            <div className="rounded-lg bg-slate-950 border border-slate-800 p-4">
              <p className="text-xs text-slate-500">
                Waiting for Retry
              </p>

              <p className="text-2xl font-bold mt-1 text-amber-400">
                {retryJobs}
              </p>
            </div>

            <div className="rounded-lg bg-slate-950 border border-slate-800 p-4">
              <p className="text-xs text-slate-500">
                Oldest Active Job
              </p>

              <p className="text-lg font-bold mt-2 font-mono">
                {oldestActiveJob
                  ? oldestActiveJob.id
                  : "None"}
              </p>
            </div>

          </div>

          <div className="mt-5 pt-5 border-t border-slate-800 flex justify-between text-sm">

            <span className="text-slate-500">
              Backlog size
            </span>

            <span className="font-semibold">
              {activeJobs} active job{activeJobs === 1 ? "" : "s"}
            </span>

          </div>

        </section>

        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">

            <h2 className="text-lg font-semibold">
              Worker Control
            </h2>

            <p className="text-sm text-slate-400 mt-1">
              Stop and restart background processing.
            </p>

            <div className="grid grid-cols-2 gap-3 mt-5">

              <button
                onClick={stopWorker}
                disabled={!workerRunning}
                className="py-3 rounded-lg bg-red-600 hover:bg-red-500 disabled:bg-slate-800 disabled:text-slate-600 font-medium"
              >
                Stop Worker
              </button>

              <button
                onClick={startWorker}
                disabled={workerRunning}
                className="py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-800 disabled:text-slate-600 font-medium"
              >
                Start Worker
              </button>

            </div>

          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">

            <div className="flex justify-between">

              <div>
                <h2 className="text-lg font-semibold">
                  Failure Injection
                </h2>

                <p className="text-sm text-slate-400 mt-1">
                  Deliberately fail jobs for testing.
                </p>
              </div>

              <span
                className={
                  failMode
                    ? "status dead"
                    : "status success"
                }
              >
                {failMode ? "FAIL MODE" : "NORMAL"}
              </span>

            </div>

            <div className="grid grid-cols-2 gap-3 mt-5">

              <button
                onClick={enableFailure}
                className="py-3 rounded-lg bg-red-600 hover:bg-red-500 font-medium"
              >
                Enable
              </button>

              <button
                onClick={disableFailure}
                className="py-3 rounded-lg bg-emerald-600 hover:bg-emerald-500 font-medium"
              >
                Disable
              </button>

            </div>

          </div>

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">

            <h2 className="text-lg font-semibold">
              Active Release
            </h2>

            <p className="text-sm text-slate-400 mt-1">
              Current deployed version
            </p>

            <p className="text-3xl font-bold text-purple-400 mt-4">
              {activeRelease
                ? activeRelease.version
                : "None"}
            </p>

            <p className="text-sm text-slate-400 mt-2">
              {activeRelease
                ? activeRelease.description
                : "No active release"}
            </p>

            <button
              onClick={rollback}
              className="w-full mt-5 py-3 rounded-lg bg-purple-600 hover:bg-purple-500 font-medium"
            >
              Rollback One Release
            </button>

          </div>

        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900 mb-8 overflow-hidden">

          <div className="px-6 py-5 border-b border-slate-800">

            <h2 className="text-lg font-semibold">
              Work State
            </h2>

            <p className="text-sm text-slate-400 mt-1">
              Accepted work and processing state
            </p>

          </div>

          <div className="overflow-x-auto">

            <table className="w-full text-sm">

              <thead className="bg-slate-950 text-slate-400">

                <tr>

                  <th className="text-left px-6 py-3">
                    Job ID
                  </th>

                  <th className="text-left px-6 py-3">
                    Type
                  </th>

                  <th className="text-left px-6 py-3">
                    Status
                  </th>

                  <th className="text-left px-6 py-3">
                    Attempts
                  </th>

                  <th className="text-left px-6 py-3">
                    Created
                  </th>

                </tr>

              </thead>

              <tbody className="divide-y divide-slate-800">

                {jobs.map(function (job) {

                  return (
                    <tr
                      key={job.id}
                      className="hover:bg-slate-800/40"
                    >

                      <td className="px-6 py-4 font-mono">
                        {job.id}
                      </td>

                      <td className="px-6 py-4 text-slate-400">
                        {job.type}
                      </td>

                      <td className="px-6 py-4">
                        <span
                          className={getStatusClass(job.status)}
                        >
                          {job.status}
                        </span>
                      </td>

                      <td className="px-6 py-4 text-slate-400">
                        {job.attempts}
                      </td>

                      <td className="px-6 py-4 text-slate-500">
                        {new Date(
                          job.created_at
                        ).toLocaleTimeString()}
                      </td>

                    </tr>
                  );

                })}

              </tbody>

            </table>

          </div>

        </section>

        <section className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">

          <div className="px-6 py-5 border-b border-slate-800">

            <h2 className="text-lg font-semibold">
              Event History
            </h2>

            <p className="text-sm text-slate-400 mt-1">
              What happened, when it happened and why
            </p>

          </div>

          <div className="max-h-96 overflow-y-auto">

            {[...events]
              .reverse()
              .map(function (event) {

                return (
                  <div
                    key={event.id}
                    className="px-6 py-4 border-b border-slate-800"
                  >

                    <div className="flex justify-between">

                      <div>
                        <span className="font-medium">
                          {event.event_type}
                        </span>

                        {event.job_id && (
                          <span className="ml-3 font-mono text-xs text-slate-500">
                            {event.job_id}
                          </span>
                        )}
                      </div>

                      <span className="text-xs text-slate-600">
                        {new Date(
                          event.created_at
                        ).toLocaleTimeString()}
                      </span>

                    </div>

                    {event.reason && (
                      <p className="text-sm text-slate-400 mt-2">
                        {event.reason}
                      </p>
                    )}

                  </div>
                );

              })}

          </div>

        </section>

      </main>

      <footer className="border-t border-slate-800 mt-10">

        <div className="max-w-7xl mx-auto px-6 py-5 flex justify-between text-xs text-slate-600">

          <span>
            NEXUS Infrastructure Engineering
          </span>

          <span>
            Local · Deterministic · Offline
          </span>

        </div>

      </footer>

    </div>
  );
}

export default App;