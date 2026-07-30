import { useState, useEffect } from "react";
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import apiClient from "../api/client";

const C = {
  technical: "#4C5FD5",
  problem: "#E8A33D",
  comms: "#3FA65B",
  ink: "#1E2A38",
  grid: "#EAEDF2",
  label: "#5A6478",   // labels, axis ticks, meta - readable on white
  faint: "#A3ABBA",   // truly tertiary only: rank numerals
};

// One shared label style, so the type scale stays consistent across the page.
const LABEL = "font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-[#5A6478]";

function Analytics() {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    loadAll();
  }, []);

  async function loadAll() {
    setIsLoading(true);
    setErrorMessage("");
    try {
      // All five are independent, so fire them together rather than
      // stacking five round-trips of latency.
      const [ov, tp, cr, sd, wk] = await Promise.all([
        apiClient.get("/analytics/overview"),
        apiClient.get("/analytics/technology-performance"),
        apiClient.get("/analytics/candidate-ranking"),
        apiClient.get("/analytics/skill-distribution"),
        apiClient.get("/analytics/weekly"),
      ]);
      setData({
        overview: ov.data,
        tech: tp.data,
        ranking: cr.data,
        skills: sd.data,
        weekly: wk.data,
      });
    } catch (err) {
      setErrorMessage("Couldn't reach the analytics service. Check that the backend is running, then try again.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 bg-[#F7F8FA]/90 backdrop-blur border-b border-[#EAEDF2]">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-end justify-between gap-4">
          <div>
            <p className={LABEL}>Ezitech · AutonomIQ</p>
            <h1 className="text-xl font-semibold text-slate-900 mt-0.5">Interview Analytics</h1>
          </div>
          <button
            onClick={loadAll}
            disabled={isLoading}
            className="font-mono text-[13px] font-medium px-3.5 py-1.5 rounded-md border border-[#EAEDF2] bg-white text-slate-900 hover:bg-slate-50 disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-indigo-600 transition-colors"
          >
            {isLoading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {errorMessage && (
          <div className="mb-6 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3">
            {errorMessage}
          </div>
        )}

        {isLoading && !data ? (
          <LoadingSkeleton />
        ) : data ? (
          <Dashboard data={data} />
        ) : null}
      </main>
    </div>
  );
}

function Dashboard({ data }) {
  const { overview, tech, ranking, skills, weekly } = data;

  return (
    <div className="space-y-5">
      {/* Stat rail */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <Stat label="Candidates" value={overview.total_candidates} />
        <Stat label="Interviews" value={overview.total_interviews} />
        <Stat label="Completed" value={overview.completed_interviews} tone="emerald" />
        <Stat label="Completion" value={`${overview.completion_rate_percent}%`} tone="indigo" />
        <Stat
          label="Awaiting review"
          value={overview.pending_mentor_review}
          tone="amber"
          emphasise
        />
      </div>

      {/* Technology performance - full width, it carries the most series */}
      <Panel
        eyebrow="By track"
        title="Where candidates struggle"
        note="Average score out of 10. A consistently low bar points at either a hard question set or a weak applicant pool for that track."
      >
        {tech.length === 0 ? (
          <Empty>Run an interview to start comparing tracks.</Empty>
        ) : (
          <>
            <Legend
              items={[
                { label: "Technical", color: C.technical },
                { label: "Problem solving", color: C.problem },
                { label: "Communication", color: C.comms },
              ]}
            />
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={tech} margin={{ top: 8, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid vertical={false} stroke={C.grid} />
                <XAxis
                  dataKey="technology"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 12, fill: C.label, fontFamily: "JetBrains Mono" }}
                />
                <YAxis
                  domain={[0, 10]}
                  tickLine={false}
                  axisLine={false}
                  tick={{ fontSize: 12, fill: C.label, fontFamily: "JetBrains Mono" }}
                />
                <Tooltip content={<ChartTip />} cursor={{ fill: "rgba(76,95,213,0.05)" }} />
                <Bar dataKey="avg_technical" name="Technical" fill={C.technical} radius={[3, 3, 0, 0]} />
                <Bar dataKey="avg_problem_solving" name="Problem solving" fill={C.problem} radius={[3, 3, 0, 0]} />
                <Bar dataKey="avg_communication" name="Communication" fill={C.comms} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </>
        )}
      </Panel>

      {/* Two-up row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <Panel
          eyebrow="Volume"
          title="Started vs completed"
          note="A widening gap means candidates are dropping out mid-interview."
        >
          {weekly.length === 0 ? (
            <Empty>No interviews in this period yet.</Empty>
          ) : (
            <>
              <Legend
                items={[
                  { label: "Started", color: C.technical },
                  { label: "Completed", color: C.comms },
                ]}
              />
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={weekly} margin={{ top: 8, right: 8, left: -24, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke={C.grid} />
                  <XAxis
                    dataKey="week"
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 11, fill: C.label, fontFamily: "JetBrains Mono" }}
                  />
                  <YAxis
                    allowDecimals={false}
                    tickLine={false}
                    axisLine={false}
                    tick={{ fontSize: 12, fill: C.label, fontFamily: "JetBrains Mono" }}
                  />
                  <Tooltip content={<ChartTip />} cursor={{ stroke: C.grid }} />
                  <Line
                    type="monotone" dataKey="started" name="Started"
                    stroke={C.technical} strokeWidth={2}
                    dot={{ r: 3, fill: C.technical, strokeWidth: 0 }}
                  />
                  <Line
                    type="monotone" dataKey="completed" name="Completed"
                    stroke={C.comms} strokeWidth={2}
                    dot={{ r: 3, fill: C.comms, strokeWidth: 0 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </>
          )}
        </Panel>

        <Panel
          eyebrow="Applicant pool"
          title="Skills on incoming resumes"
          note="Parsed automatically at registration."
        >
          {skills.length === 0 ? (
            <Empty>No resumes parsed yet.</Empty>
          ) : (
            <div className="space-y-2.5 pt-1">
              {skills.map((s) => {
                const max = skills[0].count || 1;
                return (
                  <div key={s.skill} className="flex items-center gap-3">
                    <span className="font-mono text-[12px] text-slate-700 w-24 shrink-0 truncate">
                      {s.skill}
                    </span>
                    <div className="flex-1 h-2 bg-[#EAEDF2] rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full bg-[#1E2A38]"
                        style={{ width: `${(s.count / max) * 100}%` }}
                      />
                    </div>
                    <span className="font-mono text-[12px] font-medium text-[#5A6478] w-6 text-right shrink-0">
                      {s.count}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </Panel>
      </div>

      {/* Ranking - the signature element */}
      <Panel
        eyebrow="Leaderboard"
        title="Candidate ranking"
        note="Scored across all three criteria. Bar length shows the overall score at a glance."
      >
        {ranking.length === 0 ? (
          <Empty>Complete an interview to populate the ranking.</Empty>
        ) : (
          <div className="overflow-x-auto -mx-6 px-6">
            <table className="w-full min-w-[760px]">
              <thead>
                <tr className="border-b border-[#EAEDF2]">
                  <th className={`${LABEL} py-2.5 pr-3 text-left w-8`}>#</th>
                  <th className={`${LABEL} py-2.5 pr-3 text-left`}>Candidate</th>
                  <th className={`${LABEL} py-2.5 pr-3 text-left`}>Track</th>
                  <th className={`${LABEL} py-2.5 pr-3 text-right`}>Tech</th>
                  <th className={`${LABEL} py-2.5 pr-3 text-right`}>Problem</th>
                  <th className={`${LABEL} py-2.5 pr-5 text-right`}>Comms</th>
                  <th className={`${LABEL} py-2.5 pr-3 text-left w-44`}>Overall</th>
                  <th className={`${LABEL} py-2.5 text-left`}>Decision</th>
                </tr>
              </thead>
              <tbody>
                {ranking.map((row, idx) => (
                  <tr
                    key={row.interview_id}
                    className="border-b border-[#F1F3F7] last:border-0 hover:bg-[#FAFBFC] transition-colors"
                  >
                    <td className="py-3 pr-3 font-mono text-[12px] text-[#A3ABBA]">
                      {String(idx + 1).padStart(2, "0")}
                    </td>
                    <td className="py-3 pr-3 text-[15px] font-medium text-slate-900">
                      {row.candidate_name}
                    </td>
                    <td className="py-3 pr-3 font-mono text-[12px] text-[#5A6478]">
                      {row.technology}
                    </td>
                    <td className="py-3 pr-3 font-mono text-[13px] text-slate-700 text-right">
                      {row.avg_technical}
                    </td>
                    <td className="py-3 pr-3 font-mono text-[13px] text-slate-700 text-right">
                      {row.avg_problem_solving}
                    </td>
                    <td className="py-3 pr-5 font-mono text-[13px] text-slate-700 text-right">
                      {row.avg_communication}
                    </td>
                    <td className="py-3 pr-3">
                      <ScoreBar score={row.overall_score} />
                    </td>
                    <td className="py-3">
                      <Decision
                        value={row.mentor_override || row.ai_recommendation}
                        isOverride={!!row.mentor_override}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  );
}

/* Signature element: score as length, not just digits. */
function ScoreBar({ score }) {
  const pct = Math.max(0, Math.min(100, (score / 10) * 100));
  const color = score >= 7 ? C.comms : score >= 4 ? C.problem : "#DC5B5B";

  return (
    <div className="flex items-center gap-2.5">
      <div className="flex-1 h-1.5 bg-[#EAEDF2] rounded-full overflow-hidden min-w-[80px]">
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="font-mono text-[13px] font-semibold text-slate-900 w-8 text-right">
        {score.toFixed(1)}
      </span>
    </div>
  );
}

function Stat({ label, value, tone, emphasise }) {
  const toneClass = {
    indigo: "text-indigo-600",
    emerald: "text-emerald-600",
    amber: "text-amber-600",
  }[tone] || "text-slate-900";

  return (
    <div
      className={`bg-white rounded-lg px-4 py-3 border border-[#EAEDF2] ${
        emphasise ? "border-l-2 border-l-amber-500" : ""
      }`}
    >
      <p className={LABEL}>{label}</p>
      <p className={`font-mono text-2xl font-semibold mt-1.5 tabular-nums ${toneClass}`}>{value}</p>
    </div>
  );
}

function Panel({ eyebrow, title, note, children }) {
  return (
    <section className="bg-white border border-[#EAEDF2] rounded-lg p-6">
      <p className={LABEL}>{eyebrow}</p>
      <h2 className="text-[15px] font-semibold text-slate-900 mt-1">{title}</h2>
      {note && (
        <p className="text-[13px] text-[#5A6478] mt-1.5 mb-4 max-w-xl leading-relaxed">{note}</p>
      )}
      {children}
    </section>
  );
}

function Legend({ items }) {
  return (
    <div className="flex flex-wrap gap-4 mb-3">
      {items.map((i) => (
        <span
          key={i.label}
          className="flex items-center gap-1.5 font-mono text-[11px] font-medium text-[#5A6478]"
        >
          <span className="w-2 h-2 rounded-sm" style={{ background: i.color }} />
          {i.label}
        </span>
      ))}
    </div>
  );
}

function ChartTip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[#1E2A38] rounded-md px-3 py-2 shadow-lg min-w-[160px]">
      <p className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em] text-white/60 mb-1.5">
        {label}
      </p>
      {payload.map((entry) => (
        <div key={entry.dataKey} className="flex items-center gap-2 text-[13px] py-0.5">
          <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: entry.color }} />
          <span className="text-white/80">{entry.name}</span>
          <span className="ml-auto font-mono text-white font-semibold">{entry.value}</span>
        </div>
      ))}
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
    <span className={`inline-block text-white font-mono text-[10px] font-semibold tracking-wide px-2 py-0.5 rounded ${color}`}>
      {isOverride && "✓ "}{String(value).replace("_", " ").toUpperCase()}
    </span>
  );
}

function Empty({ children }) {
  return <p className="text-[15px] text-slate-700 py-10 text-center">{children}</p>;
}

function LoadingSkeleton() {
  return (
    <div className="space-y-5 animate-pulse">
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        {[...Array(5)].map((_, i) => (
          <div key={i} className="bg-white border border-[#EAEDF2] rounded-lg h-[80px]" />
        ))}
      </div>
      <div className="bg-white border border-[#EAEDF2] rounded-lg h-[380px]" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="bg-white border border-[#EAEDF2] rounded-lg h-[330px]" />
        <div className="bg-white border border-[#EAEDF2] rounded-lg h-[330px]" />
      </div>
    </div>
  );
}

export default Analytics;