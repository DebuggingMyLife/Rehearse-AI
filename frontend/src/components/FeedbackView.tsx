import type { Feedback, Scoring } from "../api/client";

const SCORE_LABEL: Record<number, string> = {
  1: "Weak",
  2: "Needs work",
  3: "Fair",
  4: "Good",
  5: "Excellent",
};

export function ScoreBadge({ score }: { score: number }) {
  return (
    <div className={`score score-${score}`}>
      <span className="score-num">{score}</span>
      <span className="score-of">/5</span>
      <span className="score-label">{SCORE_LABEL[score]}</span>
    </div>
  );
}

export function RubricCoverageList({ scoring }: { scoring: Scoring }) {
  const covered = scoring.rubric_coverage.filter((c) => c.covered).length;
  return (
    <section className="fb-section">
      <h4>
        Rubric coverage{" "}
        <span className="muted small">
          {covered} of {scoring.rubric_coverage.length} points
        </span>
      </h4>
      <ul className="coverage">
        {scoring.rubric_coverage.map((c, i) => (
          <li key={i} className={c.covered ? "yes" : "no"}>
            <span className="mark" aria-label={c.covered ? "Covered" : "Not covered"}>
              {c.covered ? "✓" : "✗"}
            </span>
            <div>
              <div>{c.point}</div>
              {c.covered && c.quote_verified && <q className="quote">{c.evidence_quote}</q>}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Pending({ label }: { label: string }) {
  return <p className="muted small pending">{label}…</p>;
}

export function FeedbackSections({ feedback, streaming }: { feedback: Partial<Feedback>; streaming: boolean }) {
  const f = feedback;
  return (
    <>
      {f.previous_attempt_comparison && (
        <section className="fb-section comparison">
          <h4>
            Compared with attempt {f.previous_attempt_comparison.previous_attempt_number ?? "before"}
          </h4>
          <p>{f.previous_attempt_comparison.summary}</p>
          {f.previous_attempt_comparison.addressed.length > 0 && (
            <>
              <div className="sub">Now addressed</div>
              <ul className="ticks yes">
                {f.previous_attempt_comparison.addressed.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </>
          )}
          {f.previous_attempt_comparison.not_addressed.length > 0 && (
            <>
              <div className="sub">Still to work on</div>
              <ul className="ticks no">
                {f.previous_attempt_comparison.not_addressed.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      <section className="fb-section">
        <h4>What you did well</h4>
        {f.what_you_did_well === undefined ? (
          streaming && <Pending label="Writing feedback" />
        ) : f.what_you_did_well.length === 0 ? (
          <p className="muted">Nothing stood out as a clear strength in this answer.</p>
        ) : (
          <ul>
            {f.what_you_did_well.map((p, i) => (
              <li key={i}>
                {p.point}
                {p.quote_verified !== false && p.quote && (
                  <>
                    {" "}
                    <q className="quote">{p.quote}</q>
                  </>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="fb-section">
        <h4>What could be improved</h4>
        {f.what_could_be_improved === undefined ? (
          streaming && <Pending label="Writing" />
        ) : (
          <ol>
            {f.what_could_be_improved.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ol>
        )}
      </section>

      {(f.missed_opportunities === undefined ? streaming : f.missed_opportunities.length > 0) && (
        <section className="fb-section">
          <h4>Missed opportunities from your CV</h4>
          {f.missed_opportunities === undefined ? (
            <Pending label="Checking your CV" />
          ) : (
            <ul>
              {f.missed_opportunities.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      {f.structure_feedback && (
        <section className="fb-section">
          <h4>STAR structure</h4>
          <table className="star">
            <tbody>
              {(["situation", "task", "action", "result"] as const).map((k) => {
                const part = f.structure_feedback![k];
                return (
                  <tr key={k}>
                    <th>{k}</th>
                    <td>
                      {part.comment}
                      {part.quote && part.quote_verified !== false && <q className="quote">{part.quote}</q>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p>{f.structure_feedback.overall}</p>
        </section>
      )}

      <section className="fb-section">
        <h4>Example of a stronger answer</h4>
        {f.example_stronger_answer === undefined ? (
          streaming && <Pending label="Drafting" />
        ) : (
          <>
            <blockquote className="example">{f.example_stronger_answer}</blockquote>
            <p className="muted small">
              Built only from your CV and what you said.
              {f.example_answer_sentences_removed
                ? ` ${f.example_answer_sentences_removed} sentence${
                    f.example_answer_sentences_removed > 1 ? "s" : ""
                  } with details not in your CV were removed.`
                : ""}
            </p>
          </>
        )}
      </section>
    </>
  );
}
