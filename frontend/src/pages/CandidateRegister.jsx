import { useState } from "react";
import { useNavigate } from "react-router-dom";
import apiClient from "../api/client";

const TECHNOLOGIES = [
  "AI", "MERN", "Laravel", "Flutter", "Python",
  "DevOps", "UIUX", "SQL", "Data_Structures", "System_Design",
];

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

  function handleFileChange(e) {
    setResumeFile(e.target.files[0]);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setErrorMessage("");

    if (!resumeFile) {
      setErrorMessage("Please attach a resume (PDF or DOCX).");
      return;
    }

    setIsSubmitting(true);

    try {
      // Step 1: register the candidate
      const registerPayload = new FormData();
      registerPayload.append("full_name", formData.full_name);
      registerPayload.append("email", formData.email);
      registerPayload.append("technology", formData.technology);
      registerPayload.append("experience_level", formData.experience_level);
      registerPayload.append("resume", resumeFile);

      const registerResponse = await apiClient.post("/candidates/register", registerPayload, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      const candidateId = registerResponse.data.id;

      // Step 2: immediately start the interview for this candidate
      const startResponse = await apiClient.post("/interviews/start", {
        candidate_id: candidateId,
      });

      const interviewId = startResponse.data.interview_id;

      // Step 3: navigate to the interview room, carrying the first question with us
      navigate(`/interview/${interviewId}`, {
        state: {
          firstQuestion: startResponse.data.question,
          difficulty: startResponse.data.difficulty,
        },
      });
    } catch (err) {
      const detail = err.response?.data?.detail || "Something went wrong. Please try again.";
      setErrorMessage(detail);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="max-w-xl mx-auto mt-12 px-6">
      <h1 className="text-2xl font-bold text-slate-900 mb-1">Candidate Registration</h1>
      <p className="text-sm text-slate-500 mb-8">
        Register to begin your AI-conducted technical interview.
      </p>

      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-slate-900 mb-1">Full Name</label>
          <input
            type="text"
            name="full_name"
            value={formData.full_name}
            onChange={handleFieldChange}
            required
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-600"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-900 mb-1">Email</label>
          <input
            type="email"
            name="email"
            value={formData.email}
            onChange={handleFieldChange}
            required
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-600"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-900 mb-1">Technology Track</label>
          <select
            name="technology"
            value={formData.technology}
            onChange={handleFieldChange}
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-600"
          >
            {TECHNOLOGIES.map((tech) => (
              <option key={tech} value={tech}>{tech}</option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-900 mb-1">Experience Level</label>
          <select
            name="experience_level"
            value={formData.experience_level}
            onChange={handleFieldChange}
            className="w-full border border-slate-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-600"
          >
            <option value="junior">Junior</option>
            <option value="mid">Mid</option>
            <option value="senior">Senior</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-900 mb-1">Resume (PDF or DOCX)</label>
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileChange}
            required
            className="w-full text-sm text-slate-600 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:bg-indigo-600 file:text-white file:text-sm hover:file:bg-indigo-700"
          />
        </div>

        {errorMessage && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-3 py-2">
            {errorMessage}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full bg-indigo-600 text-white font-medium py-2.5 rounded-md hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSubmitting ? "Starting your interview..." : "Register & Start Interview"}
        </button>
      </form>
    </div>
  );
}

export default CandidateRegister;
