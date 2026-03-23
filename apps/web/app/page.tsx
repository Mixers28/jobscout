import { fetchFromApi } from "./lib/api";

type InboxJob = {
  id: number;
  title: string;
  company: string;
  location_text: string | null;
  url: string;
  fetched_at: string;
  decision: "skip" | "review" | "apply";
  total_score: number;
  top_reasons: string[];
  missing_keywords: string[];
  applied_at: string | null;
  stage: "new" | "applied" | "screening" | "interview" | "offer" | "closed";
  reminder_at: string | null;
  outcome: "pending" | "callback" | "rejected" | "offer" | "accepted" | "declined";
};

type SchedulerRun = {
  run_id: string;
  status: "success" | "failed";
  attempts: number;
  started_at: string;
  completed_at: string;
  error: string | null;
};

type SourceConversion = {
  source_id: number | null;
  source_name: string;
  total_jobs: number;
  apply_count: number;
  callback_count: number;
  apply_rate: number;
  callback_rate: number;
};

type AnalyticsSummary = {
  total_jobs: number;
  applied_jobs: number;
  callback_jobs: number;
  average_score: number;
  average_callback_score: number;
  source_conversion_rates: SourceConversion[];
};

type SearchParams = {
  decision?: "skip" | "review" | "apply";
  sort_by?: "fetched_at" | "score";
};

async function getHealth(): Promise<string> {
  try {
    const response = await fetchFromApi("/health", { cache: "no-store" });
    if (!response.ok) {
      return "api_unavailable";
    }
    return "ok";
  } catch {
    return "api_unavailable";
  }
}

async function getInbox(decision?: string, sortBy?: string): Promise<InboxJob[]> {
  const params = new URLSearchParams();
  if (decision) {
    params.set("decision", decision);
  }
  if (sortBy) {
    params.set("sort_by", sortBy);
  }
  const query = params.size > 0 ? `?${params.toString()}` : "";
  try {
    const response = await fetchFromApi(`/jobs/inbox${query}`, { cache: "no-store" });
    if (!response.ok) {
      return [];
    }
    return (await response.json()) as InboxJob[];
  } catch {
    return [];
  }
}

async function getSchedulerRuns(): Promise<SchedulerRun[]> {
  try {
    const response = await fetchFromApi("/jobs/schedule/runs?limit=5", {
      cache: "no-store",
    });
    if (!response.ok) {
      return [];
    }
    return (await response.json()) as SchedulerRun[];
  } catch {
    return [];
  }
}

async function getAnalyticsSummary(): Promise<AnalyticsSummary | null> {
  try {
    const response = await fetchFromApi("/jobs/analytics/summary", { cache: "no-store" });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as AnalyticsSummary;
  } catch {
    return null;
  }
}

export default async function Page({ searchParams }: { searchParams?: SearchParams }) {
  const selectedDecision = searchParams?.decision;
  const selectedSort = searchParams?.sort_by || "score";
  const [apiHealth, jobs, schedulerRuns, analytics] = await Promise.all([
    getHealth(),
    getInbox(selectedDecision, selectedSort),
    getSchedulerRuns(),
    getAnalyticsSummary(),
  ]);

  return (
    <main>
      <h1>JobScout Dashboard</h1>
      <p>Sprint 4 scheduling, tracking, and analytics view is active.</p>
      <p>API health: {apiHealth}</p>
      <p>
        <a href="/ops">Open Ops Console (register sources + run pipeline)</a>
      </p>
      <form action="/api/schedule-run" method="post">
        <button type="submit">run scheduled pipeline now</button>
      </form>

      <h2>Sprint 4 Analytics</h2>
      {analytics ? (
        <>
          <p>
            total jobs: {analytics.total_jobs}
            {" | "}
            applied: {analytics.applied_jobs}
            {" | "}
            callbacks: {analytics.callback_jobs}
            {" | "}
            avg score: {analytics.average_score.toFixed(2)}
            {" | "}
            avg callback score: {analytics.average_callback_score.toFixed(2)}
          </p>
          <ul>
            {analytics.source_conversion_rates.map((source) => (
              <li key={`${source.source_id ?? "none"}-${source.source_name}`}>
                {source.source_name}: apply {source.apply_rate.toFixed(2)}% ({source.apply_count}/{source.total_jobs})
                {" | "}
                callback {source.callback_rate.toFixed(2)}% ({source.callback_count}/{source.total_jobs})
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p>analytics unavailable</p>
      )}

      <h2>Scheduled Runs</h2>
      {schedulerRuns.length > 0 ? (
        <ul>
          {schedulerRuns.map((run) => (
            <li key={run.run_id}>
              {run.status}
              {" | attempts: "}
              {run.attempts}
              {" | started: "}
              {run.started_at}
              {" | error: "}
              {run.error || "none"}
            </li>
          ))}
        </ul>
      ) : (
        <p>no scheduler runs logged yet</p>
      )}

      <p>
        Sort:
        {" "}
        <a href="/?sort_by=score">score</a>
        {" | "}
        <a href="/?sort_by=fetched_at">newest</a>
      </p>
      <p>
        Filter:
        {" "}
        <a href="/">all</a>
        {" | "}
        <a href="/?decision=review">review</a>
        {" | "}
        <a href="/?decision=apply">apply</a>
        {" | "}
        <a href="/?decision=skip">skip</a>
      </p>
      <ul>
        {jobs.map((job) => (
          <li key={job.id}>
            <a href={job.url} target="_blank" rel="noreferrer">
              {job.title}
            </a>
            {" - "}
            {job.company}
            {" - "}
            {job.location_text || "location n/a"}
            {" - "}
            {job.decision}
            {" - score: "}
            {job.total_score.toFixed(2)}
            {" - "}
            stage: {job.stage}
            {" - "}
            outcome: {job.outcome}
            {" - "}
            <a href={`/pack/${job.id}`}>review pack</a>
            {" "}
            <form action="/api/decision" method="post" style={{ display: "inline-block", marginLeft: "8px" }}>
              <input type="hidden" name="job_id" value={job.id} />
              <button type="submit" name="decision" value="skip">skip</button>
              <button type="submit" name="decision" value="review">review</button>
              <button type="submit" name="decision" value="apply">apply</button>
            </form>
            <form action="/api/tracking" method="post" style={{ display: "inline-block", marginLeft: "8px" }}>
              <input type="hidden" name="job_id" value={job.id} />
              <select name="stage" defaultValue={job.stage}>
                <option value="new">new</option>
                <option value="applied">applied</option>
                <option value="screening">screening</option>
                <option value="interview">interview</option>
                <option value="offer">offer</option>
                <option value="closed">closed</option>
              </select>
              <select name="outcome" defaultValue={job.outcome}>
                <option value="pending">pending</option>
                <option value="callback">callback</option>
                <option value="rejected">rejected</option>
                <option value="offer">offer</option>
                <option value="accepted">accepted</option>
                <option value="declined">declined</option>
              </select>
              <button type="submit">save tracking</button>
            </form>
            {job.applied_at ? <div>applied at: {job.applied_at}</div> : null}
            {job.reminder_at ? <div>reminder at: {job.reminder_at}</div> : null}
            {job.top_reasons.length > 0 ? (
              <div>
                reasons: {job.top_reasons.join(" | ")}
              </div>
            ) : null}
            {job.missing_keywords.length > 0 ? (
              <div>
                missing: {job.missing_keywords.join(", ")}
              </div>
            ) : null}
          </li>
        ))}
      </ul>
    </main>
  );
}
