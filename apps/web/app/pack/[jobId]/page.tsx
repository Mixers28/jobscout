import { fetchFromApi } from "../../lib/api";

type EvidenceRef = {
  source: "skills_profile" | "truth_bank";
  path: string;
  quote: string;
};

type ScreeningAnswer = {
  question: string;
  answer: string;
  evidence_refs: EvidenceRef[];
};

type Claim = {
  id: string;
  text: string;
  evidence_refs: EvidenceRef[];
  supported: boolean;
};

type NeedsUserInput = {
  field: string;
  reason: string;
};

type ApplicationPack = {
  pack_id: number;
  job_id: number;
  created_at: string;
  status: "OK" | "NEEDS_USER_INPUT";
  cv_variant_md: string;
  cover_letter_md: string;
  screening_answers: ScreeningAnswer[];
  claims: Claim[];
  needs_user_input: NeedsUserInput[];
  missing_requirements: string[];
};

async function getPack(jobId: string): Promise<ApplicationPack | null> {
  try {
    const response = await fetchFromApi(`/jobs/${encodeURIComponent(jobId)}/pack`, {
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as ApplicationPack;
  } catch {
    return null;
  }
}

export default async function PackPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  const pack = await getPack(jobId);

  if (!pack) {
    return (
      <main>
        <h1>Application Pack</h1>
        <p>No pack found for job {jobId}.</p>
        <p>
          <a href="/">Back to inbox</a>
        </p>
      </main>
    );
  }

  return (
    <main>
      <h1>Application Pack Review</h1>
      <p>
        Job ID: {pack.job_id} | Pack ID: {pack.pack_id} | Status: {pack.status}
      </p>
      <p>Created at: {pack.created_at}</p>
      <p>
        <a href="/">Back to inbox</a>
      </p>

      {pack.needs_user_input.length > 0 ? (
        <>
          <h2>Needs User Input</h2>
          <ul>
            {pack.needs_user_input.map((item) => (
              <li key={`${item.field}-${item.reason}`}>
                <strong>{item.field}:</strong> {item.reason}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {pack.missing_requirements.length > 0 ? (
        <>
          <h2>Missing Keywords</h2>
          <p>{pack.missing_requirements.join(", ")}</p>
        </>
      ) : null}

      <h2>CV Variant (Markdown)</h2>
      <pre>{pack.cv_variant_md}</pre>

      <h2>Cover Letter (Markdown)</h2>
      <pre>{pack.cover_letter_md}</pre>

      <h2>Screening Answers</h2>
      <ul>
        {pack.screening_answers.map((answer, idx) => (
          <li key={`${answer.question}-${idx}`}>
            <p>
              <strong>Q:</strong> {answer.question}
            </p>
            <p>
              <strong>A:</strong> {answer.answer}
            </p>
            <p>
              <strong>Evidence:</strong>{" "}
              {answer.evidence_refs.map((ref) => `${ref.source}:${ref.path}`).join(" | ")}
            </p>
          </li>
        ))}
      </ul>

      <h2>Claims Evidence Map</h2>
      <ul>
        {pack.claims.map((claim) => (
          <li key={claim.id}>
            <p>
              <strong>{claim.id}</strong> ({claim.supported ? "supported" : "unsupported"}): {claim.text}
            </p>
            <p>
              {claim.evidence_refs.map((ref) => `${ref.source}:${ref.path}`).join(" | ")}
            </p>
          </li>
        ))}
      </ul>
    </main>
  );
}
