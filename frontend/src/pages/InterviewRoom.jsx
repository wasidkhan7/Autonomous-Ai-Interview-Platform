import { useState, useEffect, useRef } from "react";
import { useParams, useLocation } from "react-router-dom";
import apiClient from "../api/client";

function InterviewRoom() {
  const { interviewId } = useParams();
  const location = useLocation();

  // conversation is an array of { role: "agent" | "candidate", content: string }
  const [conversation, setConversation] = useState([]);
  const [currentAnswer, setCurrentAnswer] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isCompleted, setIsCompleted] = useState(false);
  const [report, setReport] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");

  const bottomRef = useRef(null);

  // On first load, seed the conversation with the question we already got
  // from CandidateRegister — avoids an unnecessary extra API call.
  useEffect(() => {
    const firstQuestion = location.state?.firstQuestion;
    if (firstQuestion) {
      setConversation([{ role: "agent", content: firstQuestion }]);
    }
  }, [location.state]);

  // Auto-scroll to the latest message whenever the conversation grows
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation]);

  async function handleSubmitAnswer(e) {
    e.preventDefault();
    if (!currentAnswer.trim()) return;

    setErrorMessage("");
    setIsSubmitting(true);

    // Show the candidate's answer immediately, before waiting on the API
    const answerText = currentAnswer;
    setConversation((prev) => [...prev, { role: "candidate", content: answerText }]);
    setCurrentAnswer("");

    try {
      const response = await apiClient.post(`/interviews/${interviewId}/answer`, {
        answer: answerText,
      });

      if (response.data.status === "completed") {
        setIsCompleted(true);
        setReport(response.data.report);
      } else {
        setConversation((prev) => [...prev, { role: "agent", content: response.data.question }]);
      }
    } catch (err) {
      const detail = err.response?.data?.detail || "Something went wrong. Please try again.";
      setErrorMessage(detail);
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isCompleted && report) {
    return <ReportView report={report} />;
  }

  return (
    <div className="max-w-2xl mx-auto mt-8 px-6 flex flex-col h-[calc(100vh-80px)]">
      <h1 className="text-xl font-bold text-slate-900 mb-4">Interview in Progress</h1>

      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {conversation.map((msg, idx) => (
          <ChatBubble key={idx} role={msg.role} content={msg.content} />
        ))}
        <div ref={bottomRef} />
      </div>

      {errorMessage && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-3 py-2 mb-3">
          {errorMessage}
        </div>
      )}

      <form onSubmit={handleSubmitAnswer} className="border-t border-slate-200 pt-4 pb-6 flex gap-2">
        <textarea
          value={currentAnswer}
          onChange={(e) => setCurrentAnswer(e.target.value)}
          placeholder="Type your answer..."
          rows={3}
          disabled={isSubmitting}
          className="flex-1 border border-slate-300 rounded-md px-3 py-2 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-600 disabled:bg-slate-50"
        />
        <button
          type="submit"
          disabled={isSubmitting || !currentAnswer.trim()}
          className="bg-indigo-600 text-white font-medium px-5 rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSubmitting ? "..." : "Send"}
        </button>
      </form>
    </div>
  );
}

function ChatBubble({ role, content }) {
  const isAgent = role === "agent";
  return (
    <div className={`flex ${isAgent ? "justify-start" : "justify-end"}`}>
      <div
        className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm ${
          isAgent
            ? "bg-white border border-slate-200 text-slate-900"
            : "bg-indigo-600 text-white"
        }`}
      >
        {content}
      </div>
    </div>
  );
}

function ReportView({ report }) {
  const recommendationColor = {
    recommend: "bg-emerald-600",
    review: "bg-amber-500",
    reject: "bg-red-500",
  }[report.hiring_recommendation] || "bg-slate-500";

  return (
    <div className="max-w-2xl mx-auto mt-12 px-6 pb-12">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Interview Complete</h1>
      <p className="text-sm text-slate-500 mb-6">Here's your engineering assessment report.</p>

      <div className="bg-white border border-slate-200 rounded-lg p-6 space-y-5">
        <div className="flex items-center gap-3">
          <span className={`text-white text-xs font-medium px-3 py-1 rounded-full ${recommendationColor}`}>
            {report.hiring_recommendation.toUpperCase()}
          </span>
          <span className="text-xs text-slate-500 font-mono">
            AI Confidence: {(report.ai_confidence_score * 100).toFixed(0)}%
          </span>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-slate-900 mb-1">Summary</h3>
          <p className="text-sm text-slate-700">{report.summary}</p>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-slate-900 mb-1">Strengths</h3>
          <p className="text-sm text-slate-700">{report.strengths}</p>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-slate-900 mb-1">Weaknesses</h3>
          <p className="text-sm text-slate-700">{report.weaknesses}</p>
        </div>

        <div>
          <h3 className="text-sm font-semibold text-slate-900 mb-1">Recommended Learning Plan</h3>
          <p className="text-sm text-slate-700">{report.learning_plan}</p>
        </div>
      </div>
    </div>
  );
}

export default InterviewRoom;
