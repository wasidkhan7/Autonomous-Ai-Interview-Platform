import { useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../api/client";

const LABEL = "font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-[#5A6478]";

// value must match the question-bank filename; label is what the candidate reads
const TRACKS = [
  { value: "AI", label: "Artificial Intelligence" },
  { value: "MERN", label: "MERN Stack" },
  { value: "Laravel", label: "Laravel" },
  { value: "Flutter", label: "Flutter" },
  { value: "Python", label: "Python" },
  { value: "DevOps", label: "DevOps" },
  { value: "UIUX", label: "UI / UX" },
  { value: "SQL", label: "SQL" },
  { value: "Data_Structures", label: "Data Structures" },
  { value: "System_Design", label: "System Design" },
];

const LEVELS = [
  { value: "junior", label: "Junior" },
  { value: "mid", label: "Mid-level" },
  { value: "senior", label: "Senior" },
];


const FIELD =
  "w-full border border-[#D8DDE6] rounded-md px-3 py-2.5 text-[15px] text-slate-900 bg-white " +
  "focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-indigo-600 transition-colors";

function CandidateRegister() {
  const navigate = useNavigate();

  const [formData, setFormData] = useState({
    full_name: "",
    email: "",
    technology: "AI",
    experience_level: "junior",
  });
  const [resumeFile, setResumeFile] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  function handleFieldChange(e) {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setErrorMessage("");

    if (!resumeFile) {
      setErrorMessage("Attach your resume as a PDF or DOCX to continue.");
      return;
    }

    setIsSubmitting(true);

    try {
      const payload = new FormData();
      payload.append("full_name", formData.full_name);
      payload.append("email", formData.email);
      payload.append("technology", formData.technology);
      payload.append("experience_level", formData.experience_level);
      payload.append("resume", resumeFile);

      const registerResponse = await apiClient.post("/candidates/register", payload, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const startResponse = await apiClient.post("/interviews/start", {
        candidate_id: registerResponse.data.id,
      });

      // InterviewRoom always rebuilds from the backend, so there's nothing
      // to hand over in navigation state.
      navigate(`/interview/${startResponse.data.interview_id}`);
    } catch (err) {
      setErrorMessage(err.response?.data?.detail || "Something went wrong. Try again.");
      setIsSubmitting(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-57px)] bg-[#F7F8FA] px-6 py-10">
      <div className="max-w-4xl mx-auto">
        <div className="mb-8">
          <p className={LABEL}>Ezitech · AutonomIQ</p>
          <h1 className="text-2xl font-semibold text-slate-900 mt-1">Candidate registration</h1>
          <p className="text-[15px] text-[#5A6478] mt-1.5">
            A few details, then your interview begins.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)] gap-6 items-start">
          {/* Form */}
          <form
            onSubmit={handleSubmit}
            className="bg-white border border-[#EAEDF2] rounded-lg p-6 space-y-5"
          >
            <Field label="Full name">
              <input
                type="text"
                name="full_name"
                value={formData.full_name}
                onChange={handleFieldChange}
                required
                autoComplete="name"
                className={FIELD}
              />
            </Field>

            <Field label="Email" hint="Used to identify your interview if you come back to it.">
              <input
                type="email"
                name="email"
                value={formData.email}
                onChange={handleFieldChange}
                required
                autoComplete="email"
                className={FIELD}
              />
            </Field>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Technology track">
                <Select name="technology" value={formData.technology} onChange={handleFieldChange}>
                  {TRACKS.map((t) => (
                    <option key={t.value} value={t.value}>{t.label}</option>
                  ))}
                </Select>
              </Field>

              <Field label="Experience level">
                <Select
                  name="experience_level"
                  value={formData.experience_level}
                  onChange={handleFieldChange}
                >
                  {LEVELS.map((l) => (
                    <option key={l.value} value={l.value}>{l.label}</option>
                  ))}
                </Select>
              </Field>
            </div>

            <Field label="Resume" hint="PDF or DOCX. We read it to tailor your questions.">
              <FileDrop file={resumeFile} onSelect={setResumeFile} />
            </Field>

            {errorMessage && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-[14px] rounded-md px-3 py-2.5">
                {errorMessage}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full bg-indigo-600 text-white text-[15px] font-medium py-3 rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2 transition-colors"
            >
              {isSubmitting ? "Setting up your interview…" : "Start interview"}
            </button>
          </form>

          {/* What to expect - answers the questions a candidate actually has */}
          <aside className="bg-white border border-[#EAEDF2] rounded-lg p-6">
            <p className={LABEL}>Before you start</p>
            <ul className="mt-4 space-y-4">
              <Expect n="01" title="Around six questions">
                The interviewer adapts as you go — answer well and questions get harder.
              </Expect>
              <Expect n="02" title="You'll speak your answers">
                Each question is read aloud and shown on screen. You reply using your microphone.
              </Expect>
              <Expect n="03" title="We read your resume">
                Your resume is used to tailor the questions to your experience and skills.
              </Expect>
              <Expect n="04" title="Stay on this page while answering">
                Switching tabs or windows mid-answer is recorded and shared with your mentor.
              </Expect>
              <Expect n="05" title="Your progress is saved">
                Refreshing or losing connection won't restart the interview.
              </Expect>
              <Expect n="06" title="A mentor makes the final call">
                The AI writes an assessment and a recommendation. A human reviews it before any decision.
              </Expect>
            </ul>
          </aside>
        </div>
      </div>
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <div>
      <label className="block text-[14px] font-semibold text-slate-900 mb-1.5">{label}</label>
      {children}
      {hint && <p className="text-[13px] text-[#5A6478] mt-1.5">{hint}</p>}
    </div>
  );
}

function Select({ children, ...props }) {
  return (
    <div className="relative">
      <select
        {...props}
        className={`${FIELD} appearance-none pr-9 cursor-pointer`}
      >
        {children}
      </select>
      {/* Custom chevron - the native one differs between browsers and OSes */}
      <svg
        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#5A6478]"
        viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.75"
      >
        <path d="M6 8l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

function FileDrop({ file, onSelect }) {
  return (
    <label
      className={`flex items-center gap-3 border border-dashed rounded-md px-4 py-3.5 cursor-pointer transition-colors ${
        file
          ? "border-emerald-600 bg-emerald-50/40"
          : "border-[#D8DDE6] bg-[#FAFBFC] hover:border-indigo-600 hover:bg-indigo-50/40"
      }`}
    >
      <input
        type="file"
        accept=".pdf,.docx"
        onChange={(e) => onSelect(e.target.files[0] || null)}
        className="sr-only"
      />
      <span
        className={`font-mono text-[11px] font-semibold px-2 py-1 rounded shrink-0 ${
          file ? "bg-emerald-600 text-white" : "bg-[#1E2A38] text-white"
        }`}
      >
        {file ? "ADDED" : "CHOOSE"}
      </span>
      <span className="text-[14px] text-slate-700 truncate">
        {file ? file.name : "No file chosen yet"}
      </span>
      {file && (
        <span className="ml-auto font-mono text-[11px] text-[#5A6478] shrink-0">Replace</span>
      )}
    </label>
  );
}

function Expect({ n, title, children }) {
  return (
    <li className="flex gap-3">
      <span className="font-mono text-[11px] text-[#A3ABBA] pt-0.5 shrink-0">{n}</span>
      <div>
        <p className="text-[14px] font-semibold text-slate-900">{title}</p>
        <p className="text-[14px] text-[#5A6478] mt-0.5 leading-relaxed">{children}</p>
      </div>
    </li>
  );
}

export default CandidateRegister;