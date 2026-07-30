import { useState, useEffect } from "react";
import apiClient from "../api/client";

const C = {
  grid: "#EAEDF2",
  label: "#5A6478",   // section eyebrows, meta - passes contrast on white
  answer: "#4A5568",  // candidate answer text
  faint: "#A3ABBA",   // truly tertiary only: rank numerals, rules
  emerald: "#3FA65B",
  amber: "#E8A33D",
  red: "#DC5B5B",
};

// One shared label style so the type scale stays consistent everywhere.
const LABEL = "font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-[#5A6478]";

const FILTERS = [
  { id: "awaiting", label: "Awaiting review" },
  { id: "decided", label: "Decided" },
  { id: "all", label: "All" },
];


function MentorDashboard() {
  const [reports, setReports] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [filter, setFilter] = useState("awaiting");
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    fetchReportList();
  }, []);

  async function fetchReportList() {
    setIsLoadingList(true);
    try {
      const response = await apiClient.get("/evaluation/");
      setReports(response.data);
    } catch (err) {
      setErrorMessage("Couldn't load the review queue. Check that the backend is running.");
    } finally {
      setIsLoadingList(false);
    }
  }

  async function openDetail(interviewId) {
    setSelectedId(interviewId);
    setIsLoadingDetail(true);
    setDetail(null);
    try {
      const response = await apiClient.get(`/evaluation/${interviewId}`);
      setDetail(response.data);
    } catch (err) {
      setErrorMessage("Couldn't load that report.");
    } finally {
      setIsLoadingDetail(false);
    }
  }

  async function handleDecision(interviewId, decision) {
    setIsSaving(true);
    try {
      await apiClient.patch(`/evaluation/${interviewId}/override`, { override: decision });
      await fetchReportList();
      if (selectedId === interviewId) await openDetail(interviewId);
    } catch (err) {
      setErrorMessage("Couldn't save that decision. Try again.");
    } finally {
      setIsSaving(false);
    }
  }

  const visible = reports.filter((r) => {
    if (filter === "awaiting") return !r.mentor_override;
    if (filter === "decided") return !!r.mentor_override;
    return true;
  });

  const awaitingCount = reports.filter((r) => !r.mentor_override).length;

  return (
    <div className="h-[calc(100vh-57px)] flex flex-col bg-[#F7F8FA]">
      <header className="bg-white border-b border-[#EAEDF2] px-6 py-3.5 shrink-0">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className={LABEL}>Ezitech · AutonomIQ</p>
            <h1 className="text-xl font-semibold text-slate-900 mt-0.5">Mentor Review</h1>
          </div>
          <p className="font-mono text-[13px] text-[#5A6478]">
            <span className="text-amber-600 font-semibold">{awaitingCount}</span> awaiting your decision
          </p>
        </div>
      </header>

      {errorMessage && (
        <div className="bg-red-50 border-b border-red-200 text-red-700 text-sm px-6 py-2 shrink-0">
          {errorMessage}
        </div>
      )}

      <div className="flex-1 flex overflow-hidden">
        <aside className="w-80 shrink-0 bg-white border-r border-[#EAEDF2] flex flex-col">
          <div className="px-3 py-2.5 border-b border-[#EAEDF2] flex gap-1 shrink-0">
            {FILTERS.map((f) => (
              <button
                key={f.id}
                onClick={() => setFilter(f.id)}
                className={`font-mono text-[11px] font-semibold uppercase tracking-[0.08em] px-2.5 py-1.5 rounded transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-600 ${
                  filter === f.id
                    ? "bg-[#1E2A38] text-white"
                    : "text-[#5A6478] hover:bg-slate-100"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto">
            {isLoadingList && (
              <p className="px-4 py-6 text-sm text-[#5A6478]">Loading…</p>
            )}

            {!isLoadingList && visible.length === 0 && (
              <p className="px-4 py-8 text-sm text-[#5A6478] leading-relaxed">
                {filter === "awaiting"
                  ? "Nothing waiting. Every completed interview has a decision."
                  : "No interviews here yet."}
              </p>
            )}

            {visible.map((r) => (
              <ReportRow
                key={r.interview_id}
                report={r}
                isSelected={selectedId === r.interview_id}
                onClick={() => openDetail(r.interview_id)}
              />
            ))}
          </div>
        </aside>

        <section className="flex-1 flex flex-col overflow-hidden">
          {!selectedId && <EmptyPane />}
          {isLoadingDetail && <p className="px-8 py-8 text-sm text-[#5A6478]">Loading report…</p>}
          {detail && !isLoadingDetail && (
            <ReportDetail
              report={detail}
              isSaving={isSaving}
              onDecision={(value) => handleDecision(selectedId, value)}
            />
          )}
        </section>
      </div>
    </div>
  );
}

function ReportRow({ report, isSelected, onClick }) {
  const decision = report.mentor_override || report.hiring_recommendation;
  const confidence = Math.round((report.ai_confidence_score || 0) * 100);

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-4 py-3 border-b border-[#F1F3F7] transition-colors focus:outline-none focus:bg-indigo-50 ${
        isSelected
          ? "bg-indigo-50 border-l-2 border-l-indigo-600"
          : "hover:bg-[#FAFBFC] border-l-2 border-l-transparent"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[15px] font-semibold text-slate-900 truncate">
          {report.candidate_name}
        </span>
        <Decision value={decision} isOverride={!!report.mentor_override} />
      </div>

      <div className="flex items-center gap-2 mt-1.5">
        <span className="font-mono text-[11px] text-[#5A6478] shrink-0">
          {report.technology} · {report.experience_level}
        </span>
        <div className="flex-1 h-1 bg-[#EAEDF2] rounded-full overflow-hidden min-w-[32px]">
          <div className="h-full rounded-full bg-[#A3ABBA]" style={{ width: `${confidence}%` }} />
        </div>
        <span className="font-mono text-[11px] text-[#5A6478] shrink-0 w-8 text-right">
          {confidence}%
        </span>
      </div>
    </button>
  );
}

function ReportDetail({ report, isSaving, onDecision }) {
  const decision = report.mentor_override || report.hiring_recommendation;

  return (
    <>
      <div className="flex-1 overflow-y-auto px-8 py-6">
        <div className="max-w-[1400px] mx-auto">
          <div className="flex items-start justify-between gap-4 pb-4 mb-6 border-b border-[#EAEDF2]">
            <div>
              <p className={LABEL}>
                Interview #{String(report.interview_id).padStart(3, "0")}
              </p>
              <h2 className="text-lg font-semibold text-slate-900 mt-0.5">
                Engineering assessment
              </h2>
            </div>
            <div className="text-right shrink-0">
              <Decision value={decision} isOverride={!!report.mentor_override} />
              <p className="font-mono text-[11px] text-[#5A6478] mt-1.5">
                AI confidence {Math.round((report.ai_confidence_score || 0) * 100)}%
              </p>
            </div>
          </div>

          {/* The AI's read on the left, the raw evidence on the right, so a
              mentor can check one against the other without scrolling. */}
          <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] gap-8">
            <div className="space-y-6">
              <Section title="Summary" body={report.summary} />
              <Section title="Strengths" body={report.strengths} />
              <Section title="Weaknesses" body={report.weaknesses} />
              <Section title="Recommended learning plan" body={report.learning_plan} />
            </div>

            <div>
              <p className={`${LABEL} mb-3`}>Answer-by-answer</p>
              <div className="space-y-3">
                {report.per_answer_scores.map((qa, idx) => (
                  <div key={idx} className="bg-white border border-[#EAEDF2] rounded-lg p-4">
                    <div className="flex gap-3">
                      <span className="font-mono text-[11px] text-[#A3ABBA] pt-1 shrink-0">
                        {String(idx + 1).padStart(2, "0")}
                      </span>
                      <div className="min-w-0">
                        <p className="text-[15px] font-medium text-slate-900 leading-relaxed">
                          {qa.question}
                        </p>
                            {qa.focus_loss_count > 0 && (
                          <span className="inline-block mt-1.5 font-mono text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded bg-amber-100 text-amber-800">
                            Left page {qa.focus_loss_count}×
                          </span>
                        )}

                        <p className="text-[15px] text-[#4A5568] mt-2 leading-relaxed">
                          {qa.answer || (
                            <span className="italic text-[#8A94A6]">No answer recorded</span>
                          )}
                        </p>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-4 mt-3 pt-3 border-t border-[#F1F3F7]">
                      <MiniScore label="Technical" value={qa.technical_score} />
                      <MiniScore label="Problem" value={qa.problem_solving_score} />
                      <MiniScore label="Comms" value={qa.communication_score} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="border-t border-[#EAEDF2] bg-white px-8 py-3 shrink-0">
        <div className="max-w-[1400px] mx-auto flex items-center gap-3">
          <p className={`${LABEL} mr-auto`}>Your decision</p>
          <DecisionButton
            label="Approve" onClick={() => onDecision("approve")}
            disabled={isSaving} active={report.mentor_override === "approve"} tone="emerald"
          />
          <DecisionButton
            label="Needs review" onClick={() => onDecision("needs_review")}
            disabled={isSaving} active={report.mentor_override === "needs_review"} tone="amber"
          />
          <DecisionButton
            label="Reject" onClick={() => onDecision("reject")}
            disabled={isSaving} active={report.mentor_override === "reject"} tone="red"
          />
        </div>
      </div>
    </>
  );
}

function DecisionButton({ label, onClick, disabled, active, tone }) {
  const tones = {
    emerald: active
      ? "bg-emerald-600 text-white border-emerald-600"
      : "text-emerald-700 border-[#EAEDF2] hover:bg-emerald-50",
    amber: active
      ? "bg-amber-500 text-white border-amber-500"
      : "text-amber-700 border-[#EAEDF2] hover:bg-amber-50",
    red: active
      ? "bg-red-500 text-white border-red-500"
      : "text-red-600 border-[#EAEDF2] hover:bg-red-50",
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`font-mono text-[13px] font-medium px-4 py-2 rounded-md border transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-indigo-600 ${tones[tone]}`}
    >
      {label}
    </button>
  );
}

function Section({ title, body }) {
  return (
    <div>
      <p className={LABEL}>{title}</p>
      <p className="text-[15px] text-slate-700 mt-2 leading-[1.7]">{body}</p>
    </div>
  );
}

function MiniScore({ label, value }) {
  const score = value ?? 0;
  const pct = Math.max(0, Math.min(100, (score / 10) * 100));
  const color = score >= 7 ? C.emerald : score >= 4 ? C.amber : C.red;

  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[#5A6478]">
          {label}
        </span>
        <span className="font-mono text-[13px] font-semibold text-slate-900">{score}</span>
      </div>
      <div className="h-1 bg-[#EAEDF2] rounded-full overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
    </div>
  );
}

function Decision({ value, isOverride }) {
  const color = {
    recommend: "bg-emerald-600",
    approve: "bg-emerald-600",
    review: "bg-amber-500",
    needs_review: "bg-amber-500",
    reject: "bg-red-500",
  }[value] || "bg-slate-500";

  return (
    <span className={`inline-block shrink-0 text-white font-mono text-[10px] font-semibold tracking-wide px-2 py-0.5 rounded ${color}`}>
      {isOverride && "✓ "}{String(value).replace("_", " ").toUpperCase()}
    </span>
  );
}

function EmptyPane() {
  return (
    <div className="flex-1 flex items-center justify-center px-8">
      <div className="text-center max-w-xs">
        <p className={LABEL}>No report open</p>
        <p className="text-[15px] text-slate-700 mt-2 leading-relaxed">
          Pick a candidate from the queue to read their assessment and record your decision.
        </p>
      </div>
    </div>
  );
}

export default MentorDashboard;