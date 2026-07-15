import { useState, useEffect } from "react";
import apiClient from "../api/client";

function MentorDashboard() {
  const [reports, setReports] = useState([]);
  const [selectedInterviewId, setSelectedInterviewId] = useState(null);
  const [detailReport, setDetailReport] = useState(null);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
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
      setErrorMessage("Failed to load interview reports.");
    } finally {
      setIsLoadingList(false);
    }
  }

  async function openDetail(interviewId) {
    setSelectedInterviewId(interviewId);
    setIsLoadingDetail(true);
    setDetailReport(null);
    try {
      const response = await apiClient.get(`/evaluation/${interviewId}`);
      setDetailReport(response.data);
    } catch (err) {
      setErrorMessage("Failed to load report detail.");
    } finally {
      setIsLoadingDetail(false);
    }
  }

  async function handleOverride(interviewId, overrideValue) {
    try {
      await apiClient.patch(`/evaluation/${interviewId}/override`, {
        override: overrideValue,
      });
      // Refresh both the list (to update the badge) and the open detail view
      await fetchReportList();
      if (selectedInterviewId === interviewId) {
        await openDetail(interviewId);
      }
    } catch (err) {
      setErrorMessage("Failed to update mentor override.");
    }
  }

  return (
    <div className="flex h-[calc(100vh-64px)]">
      {/* Left rail: list of all interviews */}
      <div className="w-96 border-r border-slate-200 bg-white overflow-y-auto">
        <div className="p-4 border-b border-slate-200">
          <h2 className="font-semibold text-slate-900">Interview Reports</h2>
          <p className="text-xs text-slate-500 mt-0.5">{reports.length} completed</p>
        </div>

        {isLoadingList && <p className="p-4 text-sm text-slate-500">Loading...</p>}

        {!isLoadingList && reports.length === 0 && (
          <p className="p-4 text-sm text-slate-500">No completed interviews yet.</p>
        )}

        {reports.map((r) => (
          <button
            key={r.interview_id}
            onClick={() => openDetail(r.interview_id)}
            className={`w-full text-left p-4 border-b border-slate-100 hover:bg-slate-50 transition-colors ${
              selectedInterviewId === r.interview_id ? "bg-indigo-50" : ""
            }`}
          >
            <div className="flex justify-between items-start mb-1">
              <span className="font-medium text-sm text-slate-900">{r.candidate_name}</span>
              <RecommendationBadge value={r.mentor_override || r.hiring_recommendation} isOverride={!!r.mentor_override} />
            </div>
            <p className="text-xs text-slate-500">{r.technology} · {r.experience_level}</p>
            <p className="text-xs text-slate-400 font-mono mt-1">
              AI confidence: {(r.ai_confidence_score * 100).toFixed(0)}%
            </p>
          </button>
        ))}
      </div>

      {/* Right pane: selected report detail */}
      <div className="flex-1 overflow-y-auto p-8">
        {errorMessage && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-3 py-2 mb-4">
            {errorMessage}
          </div>
        )}

        {!selectedInterviewId && (
          <p className="text-slate-400 text-sm">Select an interview from the list to view its report.</p>
        )}

        {isLoadingDetail && <p className="text-sm text-slate-500">Loading report...</p>}

        {detailReport && !isLoadingDetail && (
          <ReportDetail
            report={detailReport}
            onOverride={(value) => handleOverride(selectedInterviewId, value)}
          />
        )}
      </div>
    </div>
  );
}

function RecommendationBadge({ value, isOverride }) {
  const colorMap = {
    recommend: "bg-emerald-600",
    approve: "bg-emerald-600",
    review: "bg-amber-500",
    needs_review: "bg-amber-500",
    reject: "bg-red-500",
  };
  const color = colorMap[value] || "bg-slate-400";

  return (
    <span className={`text-white text-[10px] font-medium px-2 py-0.5 rounded-full ${color}`}>
      {isOverride && "✓ "}{value.replace("_", " ").toUpperCase()}
    </span>
  );
}

function ReportDetail({ report, onOverride }) {
  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-3 mb-6">
        <RecommendationBadge
          value={report.mentor_override || report.hiring_recommendation}
          isOverride={!!report.mentor_override}
        />
        <span className="text-xs text-slate-500 font-mono">
          AI Confidence: {(report.ai_confidence_score * 100).toFixed(0)}%
        </span>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-6 space-y-5 mb-6">
        <Section title="Summary" content={report.summary} />
        <Section title="Strengths" content={report.strengths} />
        <Section title="Weaknesses" content={report.weaknesses} />
        <Section title="Recommended Learning Plan" content={report.learning_plan} />
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-6 mb-6">
        <h3 className="text-sm font-semibold text-slate-900 mb-3">Per-Answer Scores</h3>
        <div className="space-y-4">
          {report.per_answer_scores.map((qa, idx) => (
            <div key={idx} className="border-b border-slate-100 last:border-0 pb-3 last:pb-0">
              <p className="text-sm text-slate-900 font-medium mb-1">{qa.question}</p>
              <p className="text-sm text-slate-600 mb-2">{qa.answer || "(no answer given)"}</p>
              <div className="flex gap-4 text-xs font-mono text-slate-500">
                <span>Technical: {qa.technical_score}/10</span>
                <span>Problem Solving: {qa.problem_solving_score}/10</span>
                <span>Communication: {qa.communication_score}/10</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-slate-900 mb-3">Mentor Decision</h3>
        <div className="flex gap-2">
          <button
            onClick={() => onOverride("approve")}
            className="flex-1 bg-emerald-600 text-white text-sm font-medium py-2 rounded-md hover:bg-emerald-700 transition-colors"
          >
            Approve
          </button>
          <button
            onClick={() => onOverride("needs_review")}
            className="flex-1 bg-amber-500 text-white text-sm font-medium py-2 rounded-md hover:bg-amber-600 transition-colors"
          >
            Needs Review
          </button>
          <button
            onClick={() => onOverride("reject")}
            className="flex-1 bg-red-500 text-white text-sm font-medium py-2 rounded-md hover:bg-red-600 transition-colors"
          >
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}

function Section({ title, content }) {
  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-900 mb-1">{title}</h3>
      <p className="text-sm text-slate-700">{content}</p>
    </div>
  );
}

export default MentorDashboard;
