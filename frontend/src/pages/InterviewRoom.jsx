import { useState, useEffect, useRef } from "react";
import { useParams, useLocation } from "react-router-dom";
import apiClient from "../api/client";

function InterviewRoom() {
  const { interviewId } = useParams();
  const location = useLocation();

  const [conversation, setConversation] = useState([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isCompleted, setIsCompleted] = useState(false);
  const [report, setReport] = useState(null);
  const [errorMessage, setErrorMessage] = useState("");
  const [needsManualPlay, setNeedsManualPlay] = useState(false);
  const [hasSpoken, setHasSpoken] = useState(false);
  const [isQuestionPlaying, setIsQuestionPlaying] = useState(false);

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


  useEffect(() => {
    const firstQuestion = location.state?.firstQuestion;
    const firstAudioUrl = location.state?.firstAudioUrl;

    if (firstQuestion) {
      setConversation([{ role: "agent", content: firstQuestion, audioUrl: firstAudioUrl }]);
      if (firstAudioUrl && audioPlayerRef.current) {
        audioPlayerRef.current.src = `http://localhost:8000${firstAudioUrl}`;
        audioPlayerRef.current.play().catch(() => setNeedsManualPlay(true));
      }
    } else {
      // No navigation state = page refresh or direct load. Rebuild from backend.
      resumeInterview();
    }

    return () => {
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
      setConversation(response.data.conversation);
      setNeedsManualPlay(true);
    } catch (err) {
      setErrorMessage("Could not restore this interview. It may not exist or may have expired.");
    }
  }

  function playAudio(audioUrl) {
    if (!audioUrl || !audioPlayerRef.current) return;
    audioPlayerRef.current.src = `http://localhost:8000${audioUrl}`;
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
    hasSpokenRef.current = false;
    gotServerMessageRef.current = false;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const ws = new WebSocket(`ws://localhost:8000/voice/interviews/${interviewId}/answer-stream`);
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
          setErrorMessage("Your browser doesn't support a compatible audio format.");
          isStartingRef.current = false;
          ws.close();
          return;
        }

        let mediaRecorder;
        try {
          mediaRecorder = new MediaRecorder(stream, { mimeType: supportedMimeType });
        } catch (err) {
          setErrorMessage("Could not start audio recording on this browser.");
          isStartingRef.current = false;
          ws.close();
          return;
        }

        mediaRecorderRef.current = mediaRecorder;

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) ws.send(e.data);
        };

        mediaRecorder.onerror = (event) => {
          setErrorMessage("Recording error: " + event.error.message);
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
          setErrorMessage("Lost connection to the interview server. Please click Start Speaking to try again.");
        }
        isStartingRef.current = false;
        setIsTranscribing(false);
      };

      ws.onclose = () => {
        isStartingRef.current = false;
      };

      ws.onmessage = (event) => handleServerMessage(JSON.parse(event.data));
    } catch (err) {
      setErrorMessage("Could not access microphone. Please allow mic permission.");
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
    const SILENCE_THRESHOLD = 20;        // above typical mic noise floor
    const SILENCE_DURATION_MS = 6000;    // quiet this long -> auto-submit
    const FRAMES_TO_CONFIRM_SPEECH = 12; // ~0.2s of sustained sound

    let loudFrameCount = 0;

    function checkVolume() {
      if (!mediaRecorderRef.current || mediaRecorderRef.current.state !== "recording") return;

      analyser.getByteFrequencyData(dataArray);
      const averageVolume = dataArray.reduce((sum, v) => sum + v, 0) / dataArray.length;

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

  function finalizeAnswer() {
    // Read the REF, not the state - this is called from a setTimeout closure.
    if (!isRecordingRef.current) return;

    if (!hasSpokenRef.current) {
      // Nothing was ever spoken - don't send an empty answer to the backend.
      // Keep recording so they can just start talking.
      setErrorMessage("I didn't hear anything yet - please speak your answer.");
      return;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "finalize" }));
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
    isRecordingRef.current = false;
    setIsRecording(false);
  }

  function handleServerMessage(data) {
    gotServerMessageRef.current = true;

    if (data.type === "final_transcript") {
      setConversation((prev) => [...prev, { role: "candidate", content: data.text }]);
      setIsTranscribing(false);
    }

    if (data.type === "next_question") {
      setConversation((prev) => [
        ...prev,
        { role: "agent", content: data.question, audioUrl: data.audio_url },
      ]);
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

  return (
    <div className="max-w-2xl mx-auto mt-8 px-6 flex flex-col h-[calc(100vh-80px)]">
      <h1 className="text-xl font-bold text-slate-900 mb-4">Interview in Progress (Voice)</h1>

      <audio
        ref={audioPlayerRef}
        className="hidden"
        onPlay={() => setQuestionPlaying(true)}
        onEnded={() => setQuestionPlaying(false)}
        onPause={() => setQuestionPlaying(false)}
        onError={() => setQuestionPlaying(false)}
      />

      {needsManualPlay && (
        <button
          onClick={playCurrentPendingQuestion}
          className="mb-3 bg-slate-200 text-slate-900 text-sm px-4 py-2 rounded-md hover:bg-slate-300 self-start"
        >
          🔊 Play Current Question
        </button>
      )}

      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {conversation.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === "agent" ? "justify-start" : "justify-end"}`}>
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2.5 text-sm ${
                msg.role === "agent"
                  ? "bg-white border border-slate-200 text-slate-900"
                  : "bg-indigo-600 text-white"
              }`}
            >
              {msg.content}
              {msg.role === "agent" && msg.audioUrl && (
                <button
                  onClick={() => playAudio(msg.audioUrl)}
                  className="ml-2 text-xs text-indigo-600 underline"
                >
                  Replay
                </button>
              )}
            </div>
          </div>
        ))}

        {isRecording && (
          <div className="flex justify-end">
            <div className="rounded-lg px-4 py-2.5 text-sm bg-indigo-100 text-indigo-900 italic">
              {hasSpoken ? "Listening…" : "Waiting for you to speak…"}
            </div>
          </div>
        )}

        {isTranscribing && (
          <div className="flex justify-end">
            <div className="rounded-lg px-4 py-2.5 text-sm bg-slate-200 text-slate-700 italic">
              Transcribing your answer…
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {errorMessage && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-3 py-2 mb-3">
          {errorMessage}
        </div>
      )}

      <div className="border-t border-slate-200 pt-4 pb-6 flex justify-center gap-3">
        {!isRecording ? (
          <button
            onClick={startRecording}
            disabled={isTranscribing || isQuestionPlaying}
            className="bg-indigo-600 text-white font-medium px-6 py-3 rounded-full hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isTranscribing
              ? "Processing…"
              : isQuestionPlaying
              ? "Listen to the question…"
              : "Start Speaking"}
          </button>
        ) : (
          <button
            onClick={finalizeAnswer}
            disabled={!hasSpoken}
            className="bg-emerald-600 text-white font-medium px-6 py-3 rounded-full hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {hasSpoken ? "Send Answer" : "Speak your answer…"}
          </button>
        )}
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
        <div><h3 className="text-sm font-semibold text-slate-900 mb-1">Summary</h3><p className="text-sm text-slate-700">{report.summary}</p></div>
        <div><h3 className="text-sm font-semibold text-slate-900 mb-1">Strengths</h3><p className="text-sm text-slate-700">{report.strengths}</p></div>
        <div><h3 className="text-sm font-semibold text-slate-900 mb-1">Weaknesses</h3><p className="text-sm text-slate-700">{report.weaknesses}</p></div>
        <div><h3 className="text-sm font-semibold text-slate-900 mb-1">Recommended Learning Plan</h3><p className="text-sm text-slate-700">{report.learning_plan}</p></div>
      </div>
    </div>
  );
}

export default InterviewRoom;

