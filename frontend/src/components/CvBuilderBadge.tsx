import type { Session } from "../api/client";

/** Shown on sessions started from the CV Builder: which job the CV was built for, and the
 *  requirements the questions will probe. */
export default function CvBuilderBadge({ session }: { session: Session }) {
  const ctx = session.cv_builder_context;
  if (!ctx) return null;
  return (
    <div className="builder-badge">
      <span className="tag builder-tag">
        From your CV Builder CV: {ctx.job_title}
        {session.cv_build_id && (
          <>
            {" · "}
            <a href={`#/build/${session.cv_build_id}`}>edit CV</a>
          </>
        )}
      </span>
      {ctx.missing_requirements.length > 0 && (
        <p className="small">
          <span className="muted">We'll ask about:</span> {ctx.missing_requirements.join(", ")}
        </p>
      )}
    </div>
  );
}
