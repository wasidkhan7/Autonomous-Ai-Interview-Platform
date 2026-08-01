import { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import apiClient, { API_BASE_URL, WS_BASE_URL } from "../api/client";

const LABEL = "font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-[#5A6478]";

function InterviewRoom() {
  const { interviewId } = useParams();

  const [conversation, setConversation] = useState([]);
  const [questionCount, setQuestionCount] = useState(null);
  // Total comes from the backend now - it's per-candidate (10 for junior,
  // 12 for mid/senior). 10 is just the value shown before the first payload lands.
  const [totalQuestions, setTotalQuestions] = useState(10);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isCompleted, setIsCompleted] = useState(false);
  const [report, setReport] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [needsManualPlay, setNeedsManualPlay] = useState(false);
  const [hasSpoken, setHasSpoken] = useState(false);
  const [isQuestionPlaying, setIsQuestionPlaying] = useState(false);
  const [focusLosses, setFocusLosses] = useState(0);
  const [liveCaption, setLiveCaption] = useState("");

  const wsRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioContextRef = useRef(null);
  const silenceTimerRef = useRef(null);
  const bottomRef = useRef(null);
  const audioPlayerRef = useRef(null);
  const isStartingRef = useRef(false);
  // Refs mirror the state values that CALLBACKS need to read. State inside a
  // closure (like the silence setTimeout) is frozen at capture time; refs
  // always give the current value.
  const isRecordingRef = useRef(false);
  const hasSpokenRef = useRef(false);
  const gotServerMessageRef = useRef(false);
  // Ref version for the synchronous guard inside startRecording - state
  // alone can lag behind a fast click.
  const isQuestionPlayingRef = useRef(false);
  // Written to directly from the audio loop - see checkVolume below.
  const levelBarRef = useRef(null);

  const focusLossRef = useRef(0);
  const detachFocusWatchersRef = useRef(null);




  useEffect(() => {
    // ALWAYS rebuild from the backend. location.state can't be used as a
    // "just arrived" signal - React Router stores it in the History API,
    // so it survives a refresh and would reset us to question one.
    resumeInterview();

    // Watch for the whole time a question is on screen, not just while
    // recording - the exploitable window is hearing the question, tabbing
    // away to look it up, then coming back and pressing record.
    attachFocusWatchers();

    return () => {
      if (detachFocusWatchersRef.current) detachFocusWatchersRef.current();
      if (wsRef.current) wsRef.current.close();
      stopRecording();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation, isTranscribing]);

  async function resumeInterview() {
    try {
      const response = await apiClient.get(`/interviews/${interviewId}/resume`);

      if (response.data.status === "completed") {
        setIsCompleted(true);
        setReport(response.data.report);
        return;
      }

      const restored = response.data.conversation || [];
      setConversation(restored);
      if (response.data.question_count) setQuestionCount(response.data.question_count);
      if (response.data.total_questions) setTotalQuestions(response.data.total_questions);

      // Try to autoplay the pending question; browsers block autoplay without
      // a recent user gesture, so fall back to the manual button.
      const lastAgent = [...restored].reverse().find((m) => m.role === "agent");
      if (lastAgent?.audioUrl && audioPlayerRef.current) {
        audioPlayerRef.current.src = `${API_BASE_URL}${lastAgent.audioUrl}`;
        audioPlayerRef.current.play().catch(() => setNeedsManualPlay(true));
      } else {
        setNeedsManualPlay(true);
      }
    } catch (err) {
      setErrorMessage("Couldn't load this interview. Refresh the page, or contact your mentor.");
    }
  }

  function playAudio(audioUrl) {
    if (!audioUrl || !audioPlayerRef.current) return;
    audioPlayerRef.current.src = `${API_BASE_URL}${audioUrl}`;
    audioPlayerRef.current.play().catch(() => {});
  }

  function setQuestionPlaying(playing) {
    isQuestionPlayingRef.current = playing;
    setIsQuestionPlaying(playing);
  }

  function playCurrentPendingQuestion() {
    const lastAgentMsg = [...conversation].reverse().find((m) => m.role === "agent");
    if (lastAgentMsg?.audioUrl) playAudio(lastAgentMsg.audioUrl);
    setNeedsManualPlay(false);
  }

  async function startRecording() {
    // Don't let the mic open while the question is being read aloud -
    // otherwise the speakers bleed into the mic and Whisper transcribes
    // the interviewer's own question as the candidate's answer.
    if (isStartingRef.current || isRecording || isTranscribing || isQuestionPlayingRef.current) return;

    isStartingRef.current = true;

    setErrorMessage("");
    setHasSpoken(false);
    // setLiveCaption("");
    hasSpokenRef.current = false;
    gotServerMessageRef.current = false;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ws = new WebSocket(`${WS_BASE_URL}/voice/interviews/${interviewId}/answer-stream`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (ws.readyState !== WebSocket.OPEN) {
          isStartingRef.current = false;
          return;
        }

        const preferredMimeTypes = [
          "audio/webm;codecs=opus",
          "audio/webm",
          "audio/ogg;codecs=opus",
          "audio/ogg",
        ];
        const supportedMimeType = preferredMimeTypes.find((t) => MediaRecorder.isTypeSupported(t));

        if (!supportedMimeType) {
          setErrorMessage("This browser can't record audio. Try Chrome or Firefox.");
          isStartingRef.current = false;
          ws.close();
          return;
        }

        let mediaRecorder;
        try {
          mediaRecorder = new MediaRecorder(stream, { mimeType: supportedMimeType });
        } catch (err) {
          setErrorMessage("Couldn't start recording on this browser.");
          isStartingRef.current = false;
          ws.close();
          return;
        }

        mediaRecorderRef.current = mediaRecorder;

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) ws.send(e.data);
        };

        mediaRecorder.onerror = (event) => {
          setErrorMessage("Recording stopped unexpectedly: " + event.error.message);
        };

        mediaRecorder.start(1000);
        setIsRecording(true);
        isRecordingRef.current = true;
        isStartingRef.current = false;
        setupSilenceDetection(stream);
      };

      ws.onerror = () => {
        // Only show a generic message if the server never told us anything.
        // Otherwise its specific message (e.g. "No speech detected") stands.
        if (!gotServerMessageRef.current) {
          setErrorMessage("Lost connection to the interview server. Press Start speaking to retry.");
        }
        isStartingRef.current = false;
        setIsTranscribing(false);
      };

      ws.onclose = () => {
        isStartingRef.current = false;
      };

      ws.onmessage = (event) => handleServerMessage(JSON.parse(event.data));
    } catch (err) {
      setErrorMessage("Couldn't reach your microphone. Allow mic access and try again.");
      isStartingRef.current = false;
    }
  }

  function setupSilenceDetection(stream) {
    const audioContext = new AudioContext();
    audioContextRef.current = audioContext;

    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 512;
    source.connect(analyser);

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    const SILENCE_THRESHOLD = 12;        // above typical mic noise floor
    const SILENCE_DURATION_MS = 6000;    // quiet this long -> auto-submit
    const FRAMES_TO_CONFIRM_SPEECH = 12; // ~0.2s of sustained sound

    let loudFrameCount = 0;

    function checkVolume() {
      if (!mediaRecorderRef.current || mediaRecorderRef.current.state !== "recording") return;

      analyser.getByteFrequencyData(dataArray);
      const averageVolume = dataArray.reduce((sum, v) => sum + v, 0) / dataArray.length;

      // Write the mic level straight to the DOM node. Routing this through
      // React state would re-render the whole conversation 60 times a second
      // for what is a decorative bar.
      if (levelBarRef.current) {
        const pct = Math.min(100, (averageVolume / 60) * 100);
        levelBarRef.current.style.width = `${pct}%`;
      }

      if (averageVolume < SILENCE_THRESHOLD) {
        loudFrameCount = 0;
        if (!silenceTimerRef.current) {
          silenceTimerRef.current = setTimeout(finalizeAnswer, SILENCE_DURATION_MS);
        }
      } else {
        loudFrameCount += 1;
        // Only count as speech once it's SUSTAINED - a single spike from a
        // fan, a door, or a keyboard click shouldn't unlock submission.
        if (loudFrameCount >= FRAMES_TO_CONFIRM_SPEECH && !hasSpokenRef.current) {
          hasSpokenRef.current = true;
          setHasSpoken(true);
        }
        if (silenceTimerRef.current) {
          clearTimeout(silenceTimerRef.current);
          silenceTimerRef.current = null;
        }
      }

      // Keep sampling every frame - without this, volume is measured exactly
      // once and both silence detection and speech detection break.
      if (mediaRecorderRef.current?.state === "recording") {
        requestAnimationFrame(checkVolume);
      }
    }

    checkVolume();
  }

  function attachFocusWatchers() {
    let lastCountedAt = 0;

    const record = () => {
      // A single alt-tab usually fires BOTH visibilitychange and blur.
      // Collapse anything within a second into one event.
      const now = Date.now();
      if (now - lastCountedAt < 1000) return;
      lastCountedAt = now;

      focusLossRef.current += 1;
      setFocusLosses(focusLossRef.current);
    };

    const onVisibility = () => {
      if (document.hidden) record();
    };

    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", record);

    detachFocusWatchersRef.current = () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("blur", record);
    };
  }

  function finalizeAnswer() {
    // Read the REF, not the state - this is called from a setTimeout closure.
    if (!isRecordingRef.current) return;

    if (!hasSpokenRef.current) {
      // Nothing was ever spoken - don't send an empty answer to the backend.
      // Keep recording so they can just start talking.
      setErrorMessage("Nothing recorded yet. Speak your answer, then send it.");
      return;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: "finalize",
        focus_losses: focusLossRef.current,
      }));
      // Reset for the next question - the count is per-answer.
      focusLossRef.current = 0;
      setFocusLosses(0);
      setIsTranscribing(true);
    }
    stopRecording();
  }

  function stopRecording() {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach((t) => t.stop());
    }
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      audioContextRef.current.close();
    }
    if (levelBarRef.current) levelBarRef.current.style.width = "0%";

    isRecordingRef.current = false;
    setIsRecording(false);
  }

  function handleServerMessage(data) {
    gotServerMessageRef.current = true;

    if (data.type === "partial_transcript") {
      // setLiveCaption(data.text);
    }

    if (data.type === "final_transcript") {
      setConversation((prev) => [...prev, { role: "candidate", content: data.text }]);
      setIsTranscribing(false);
      setLiveCaption("");
    }

    if (data.type === "next_question") {
      setConversation((prev) => [
        ...prev,
        { role: "agent", content: data.question, audioUrl: data.audio_url },
      ]);
      if (data.question_count) setQuestionCount(data.question_count);
      if (data.total_questions) setTotalQuestions(data.total_questions);
      playAudio(data.audio_url);
      if (wsRef.current) wsRef.current.close();
    }

    if (data.type === "interview_completed") {
      setIsCompleted(true);
      setReport(data.report);
      if (wsRef.current) wsRef.current.close();
    }

    if (data.type === "error") {
      setErrorMessage(data.detail);
      setIsTranscribing(false);
      stopRecording();
    }
  }

  if (isCompleted && report) return <ReportView report={report} />;

  // Prefer the backend's count. If it isn't there yet, approximate from the
  // transcript so the progress bar still moves.
  const agentMessages = conversation.filter((m) => m.role === "agent").length;
  const displayCount = questionCount ?? Math.min(totalQuestions, Math.max(1, agentMessages));
  const progress = Math.min(100, (displayCount / totalQuestions) * 100);

  return (
    <div className="h-[calc(100vh-57px)] flex flex-col bg-[#F7F8FA]">
      <audio
        ref={audioPlayerRef}
        className="hidden"
        onPlay={() => setQuestionPlaying(true)}
        onEnded={() => setQuestionPlaying(false)}
        onPause={() => setQuestionPlaying(false)}
        onError={() => setQuestionPlaying(false)}
      />

      {/* Header - progress is what a candidate most wants to know mid-interview */}
      <header className="bg-white border-b border-[#EAEDF2] shrink-0">
        <div className="max-w-3xl mx-auto px-6 py-3.5 flex items-end justify-between gap-4">
          <div>
            <p className={LABEL}>Ezitech · AutonomIQ</p>
            <h1 className="text-xl font-semibold text-slate-900 mt-0.5">Technical interview</h1>
          </div>
          <p className="font-mono text-[13px] text-[#5A6478] shrink-0">
            Question <span className="text-slate-900 font-semibold">{displayCount}</span> of {totalQuestions}
          </p>
        </div>
        <div className="h-0.5 bg-[#EAEDF2]">
          <div
            className="h-full bg-indigo-600 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </header>

      {/* Conversation - anchored to the bottom so a short interview doesn't
          leave the messages stranded at the top of an empty screen */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-6 min-h-full flex flex-col justify-end gap-4">
          {conversation.map((msg, idx) =>
            msg.role === "agent" ? (
              <AgentBubble
                key={idx}
                message={msg}
                isLast={idx === conversation.length - 1}
                needsPlay={needsManualPlay && idx === conversation.length - 1}
                disabled={isRecording}
                onPlay={() =>
                  needsManualPlay && idx === conversation.length - 1
                    ? playCurrentPendingQuestion()
                    : playAudio(msg.audioUrl)
                }
              />
            ) : (
              <CandidateBubble key={idx} content={msg.content} />
            )
          )}

          {isRecording && liveCaption && (
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-md px-4 py-2.5 bg-indigo-100 text-indigo-900 text-[15px] italic">
                {liveCaption}…
              </div>
            </div>
          )}

          {isTranscribing && (
            <div className="flex justify-end">
              <div className="rounded-2xl rounded-br-md px-4 py-2.5 bg-[#EDEFF4] text-[#5A6478] text-[15px] italic">
                Transcribing your answer…
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Control bar */}
      <footer className="bg-white border-t border-[#EAEDF2] shrink-0">
        <div className="max-w-3xl mx-auto px-6 py-4">
          {errorMessage && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-[14px] rounded-md px-3 py-2 mb-3">
              {errorMessage}
            </div>
          )}

          {focusLosses > 0 && (
            <div className="bg-amber-50 border border-amber-200 text-amber-800 text-[13px] rounded-md px-3 py-2 mb-3">
              You left this page {focusLosses} {focusLosses === 1 ? "time" : "times"} on
              this question. This is recorded and shown to your mentor.
            </div>
          )}

          {/* Mic level - updated by direct DOM writes, not React state */}
          <div
            className={`h-1 bg-[#EAEDF2] rounded-full overflow-hidden mb-3 transition-opacity ${
              isRecording ? "opacity-100" : "opacity-0"
            }`}
          >
            <div ref={levelBarRef} className="h-full bg-emerald-600 rounded-full" style={{ width: "0%" }} />
          </div>

          <div className="flex items-center gap-4">
            <p className="text-[14px] text-[#5A6478] flex-1">
              {isQuestionPlaying
                ? "Listen to the question, then answer."
                : isTranscribing
                ? "Working on your answer…"
                : isRecording && hasSpoken
                ? "Recording. Send when you're finished, or pause and it'll send itself."
                : isRecording
                ? "Recording. Start speaking whenever you're ready."
                : "Press to answer out loud."}
            </p>

            {!isRecording ? (
              <button
                onClick={startRecording}
                disabled={isTranscribing || isQuestionPlaying}
                className="shrink-0 bg-indigo-600 text-white text-[15px] font-medium px-6 py-2.5 rounded-full hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:ring-offset-2 transition-colors"
              >
                {isTranscribing
                  ? "Processing…"
                  : isQuestionPlaying
                  ? "Question playing…"
                  : "Start speaking"}
              </button>
            ) : (
              <button
                onClick={finalizeAnswer}
                disabled={!hasSpoken}
                className="shrink-0 bg-emerald-600 text-white text-[15px] font-medium px-6 py-2.5 rounded-full hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-emerald-600 focus:ring-offset-2 transition-colors"
              >
                {hasSpoken ? "Send answer" : "Listening…"}
              </button>
            )}
          </div>
        </div>
      </footer>
    </div>
  );
}

function AgentBubble({ message, isLast, needsPlay, disabled, onPlay }) {
  return (
    <div className="flex justify-start">
      <div
        className={`max-w-[85%] rounded-2xl rounded-tl-md px-4 py-3 border ${
          isLast ? "bg-white border-[#D8DDE6]" : "bg-white/70 border-[#EAEDF2]"
        }`}
      >
        <p className={LABEL}>Interviewer</p>
        <p className="text-[15px] text-slate-900 leading-relaxed mt-1.5">{message.content}</p>
        {message.audioUrl && (
          <button
            onClick={onPlay}
            disabled={disabled}
            className={`mt-2.5 font-mono text-[11px] font-semibold uppercase tracking-wide px-2.5 py-1 rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-indigo-600 ${
              needsPlay
                ? "bg-indigo-600 text-white hover:bg-indigo-700"
                : "text-[#5A6478] bg-[#F1F3F7] hover:bg-[#E5E9F0]"
            }`}
          >
            {needsPlay ? "Play question" : "Replay"}
          </button>
        )}
      </div>
    </div>
  );
}

function CandidateBubble({ content }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-br-md px-4 py-3 bg-indigo-600">
        <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">
          You
        </p>
        <p className="text-[15px] text-white leading-relaxed mt-1.5">{content}</p>
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
    <div className="min-h-[calc(100vh-57px)] bg-[#F7F8FA] px-6 py-10">
      <div className="max-w-2xl mx-auto">
        <p className={LABEL}>Ezitech · AutonomIQ</p>
        <h1 className="text-2xl font-semibold text-slate-900 mt-1">Interview complete</h1>
        <p className="text-[15px] text-[#5A6478] mt-1.5 mb-6">
          Here's your assessment. A mentor reviews this before any decision is made.
        </p>

        <div className="bg-white border border-[#EAEDF2] rounded-lg p-6 space-y-6">
          <div className="flex items-center gap-3 pb-4 border-b border-[#EAEDF2]">
            <span
              className={`text-white font-mono text-[10px] font-semibold tracking-wide px-2 py-0.5 rounded ${recommendationColor}`}
            >
              {report.hiring_recommendation.toUpperCase()}
            </span>
            <span className="font-mono text-[11px] text-[#5A6478]">
              AI confidence {Math.round((report.ai_confidence_score || 0) * 100)}%
            </span>
          </div>

          <Section title="Summary" body={report.summary} />
          <Section title="Strengths" body={report.strengths} />
          <Section title="Weaknesses" body={report.weaknesses} />
          <Section title="Recommended learning plan" body={report.learning_plan} />
        </div>
      </div>
    </div>
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

export default InterviewRoom;
