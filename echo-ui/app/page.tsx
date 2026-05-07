"use client";

import { useEffect, useMemo, useState } from "react";
import { Mic, Volume2, Moon, Music, Play, Sparkles, Brain } from "lucide-react";

type AssistantStatus =
  | "sleeping"
  | "listening"
  | "thinking"
  | "speaking"
  | "playing";

export default function Home() {
  const [status, setStatus] = useState<AssistantStatus>("sleeping");
  const [message, setMessage] = useState("Say Echo to wake me");
  const [showSplash, setShowSplash] = useState(true);
  const [wsConnected, setWsConnected] = useState(false);

  useEffect(() => {
    const splashTimer = setTimeout(() => {
      setShowSplash(false);
    }, 5000);

    return () => clearTimeout(splashTimer);
  }, []);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8765");

    ws.onopen = () => {
      setWsConnected(true);
    };

    ws.onclose = () => {
      setWsConnected(false);
    };

    ws.onerror = () => {
      setWsConnected(false);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setStatus(data.status);
      setMessage(data.message || "");
    };

    return () => ws.close();
  }, []);

  const titleText = useMemo(() => {
    switch (status) {
      case "sleeping":
        return "Say “Echo” to wake me";
      case "listening":
        return "I’m listening";
      case "thinking":
        return "Thinking...";
      case "speaking":
        return "Speaking...";
      case "playing":
        return "Playing media";
      default:
        return "Echo AI Assistant";
    }
  }, [status]);

  return (
    <main className="min-h-screen bg-[#050816] flex items-center justify-center p-4">
      <div className="relative w-[min(100vw,100vh)] h-[min(100vw,100vh)] max-w-[1080px] max-h-[1080px] overflow-hidden rounded-[56px] border border-white/10 bg-[radial-gradient(circle_at_top,#132a57_0%,#081124_45%,#020617_100%)] shadow-[0_0_60px_rgba(0,0,0,0.45)]">
        {/* ambient background */}
        <div className="absolute inset-0">
          <div className="absolute -top-20 left-1/2 h-72 w-72 -translate-x-1/2 rounded-full bg-cyan-500/20 blur-3xl" />
          <div className="absolute bottom-12 left-10 h-44 w-44 rounded-full bg-fuchsia-500/10 blur-3xl" />
          <div className="absolute right-10 top-24 h-56 w-56 rounded-full bg-blue-500/10 blur-3xl" />
          <div className="absolute inset-0 bg-[linear-gradient(to_bottom,rgba(255,255,255,0.03),transparent_20%,transparent_80%,rgba(255,255,255,0.03))]" />
        </div>

        {/* splash */}
        {showSplash && (
          <button
            onClick={() => setShowSplash(false)}
            className="absolute inset-0 z-30 flex flex-col items-center justify-center bg-[radial-gradient(circle_at_center,rgba(10,25,50,1),rgba(2,6,23,1))] text-white"          >
            <div className="relative flex items-center justify-center">
              <div className="absolute h-64 w-64 rounded-full border border-cyan-400/30 animate-[spin_12s_linear_infinite]" />
              <div className="absolute h-80 w-80 rounded-full border border-fuchsia-400/20 animate-[spin_18s_linear_infinite_reverse]" />
              <div className="absolute h-52 w-52 rounded-full bg-cyan-400/15 blur-2xl animate-pulse" />
              <div className="relative grid h-40 w-40 place-items-center rounded-full bg-gradient-to-br from-cyan-400 via-blue-500 to-fuchsia-500 shadow-[0_0_60px_rgba(59,130,246,0.55)]">
                <div className="grid h-28 w-28 place-items-center rounded-full bg-slate-950/80">
                  <Sparkles size={44} />
                </div>
              </div>

              <div className="absolute -left-28 top-10 h-3 w-3 rounded-full bg-cyan-300 animate-bounce" />
              <div className="absolute -right-24 bottom-8 h-4 w-4 rounded-full bg-fuchsia-300 animate-pulse" />
              <div className="absolute left-10 -top-14 h-2.5 w-2.5 rounded-full bg-blue-300 animate-ping" />
            </div>

            <h1 className="mt-12 text-5xl font-extrabold tracking-wide">
              Welcome to Echo
            </h1>
            <p className="mt-4 max-w-xl text-center text-lg text-slate-300">
              Your smart voice assistant for media, search, and conversation.
            </p>

            <div className="mt-10 rounded-full border border-cyan-400/30 bg-white/5 px-6 py-3 text-sm text-slate-300">
              Tap anywhere to continue
            </div>
          </button>
        )}

        {/* main content */}
        <div className="relative z-10 flex h-full flex-col p-10 text-white">
          {/* header */}
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-wide">Echo AI Assistant</h1>
              <p className="mt-1 text-sm text-slate-300">
                Smart display UI • 1080 × 1080
              </p>
            </div>

            <div className="flex items-center gap-3">
              <div
                className={`h-3.5 w-3.5 rounded-full ${
                  wsConnected ? "bg-green-400 shadow-[0_0_16px_rgba(74,222,128,0.8)]" : "bg-red-400 shadow-[0_0_16px_rgba(248,113,113,0.8)]"
                }`}
              />
              <span className="text-sm font-medium text-slate-200">
                {wsConnected ? "Connected" : "Disconnected"}
              </span>
              <span
                className={`rounded-full px-5 py-2 text-sm font-bold tracking-wider ${badgeClass(
                  status
                )}`}
              >
                {status.toUpperCase()}
              </span>
            </div>
          </div>

          {/* center */}
          <section className="flex flex-1 flex-col items-center justify-center text-center">
            <div className="relative flex items-center justify-center">
              {/* outer animated waves */}
              {(status === "listening" || status === "speaking") && (
                <>
                  <div className="absolute h-72 w-72 rounded-full border border-cyan-400/25 animate-ping" />
                  <div className="absolute h-88 w-88 rounded-full border border-cyan-300/15 animate-pulse" />
                </>
              )}

              {status === "thinking" && (
                <>
                  <div className="absolute h-72 w-72 rounded-full border border-yellow-400/25 animate-pulse" />
                  <div className="absolute h-88 w-88 rounded-full border border-orange-300/15 animate-[spin_8s_linear_infinite]" />
                </>
              )}

              <div
                className={`relative grid h-72 w-72 place-items-center rounded-full shadow-[0_0_90px_rgba(59,130,246,0.45)] transition-all duration-500 ${orbClass(
                  status
                )} ${status === "speaking" ? "animate-pulse" : ""}`}
              >
                <div className="grid h-44 w-44 place-items-center rounded-full bg-slate-950/75 backdrop-blur-xl border border-white/10">
                  {status === "sleeping" && <Moon size={72} />}
                  {status === "listening" && <Mic size={72} />}
                  {status === "thinking" && <Brain size={72} />}
                  {status === "speaking" && <Volume2 size={72} />}
                  {status === "playing" && <Music size={72} />}
                </div>
              </div>

              {/* floating particles */}
              <div className="absolute -left-20 top-8 h-4 w-4 rounded-full bg-cyan-300/80 animate-bounce" />
              <div className="absolute -right-16 top-20 h-3 w-3 rounded-full bg-fuchsia-300/80 animate-ping" />
              <div className="absolute left-8 -bottom-8 h-3.5 w-3.5 rounded-full bg-blue-300/80 animate-pulse" />
              <div className="absolute right-10 -bottom-10 h-2.5 w-2.5 rounded-full bg-cyan-200/80 animate-bounce" />
            </div>

            <h2 className="mt-10 text-5xl font-bold">{titleText}</h2>
            <p className="mt-3 text-xl text-slate-300">{message}</p>

            <div className="mt-10 grid grid-cols-3 gap-5">
              <InfoCard
                icon={<Mic size={24} />}
                title="Microphone"
                value={wsConnected ? "Ready" : "Offline"}
              />
              <InfoCard
                icon={<Volume2 size={24} />}
                title="Speaker"
                value="Ready"
              />
              <InfoCard
                icon={<Play size={24} />}
                title="Media"
                value="YouTube / Spotify"
              />
            </div>
          </section>

          {/* footer */}
          <footer className="rounded-[28px] border border-white/10 bg-slate-950/40 p-5 backdrop-blur-md">
            <p className="text-base text-slate-200">
              <span className="font-semibold text-cyan-300">Try:</span>{" "}
              “Echo, play Believer on YouTube”
            </p>
            <p className="mt-1 text-sm text-slate-400">
              Voice states: sleeping • listening • thinking • speaking • playing
            </p>
          </footer>
        </div>
      </div>
    </main>
  );
}

function InfoCard({
  icon,
  title,
  value,
}: {
  icon: React.ReactNode;
  title: string;
  value: string;
}) {
  return (
    <div className="flex w-[250px] flex-col gap-3 rounded-[28px] border border-white/10 bg-white/5 p-5 text-left backdrop-blur-md">
      <div className="text-cyan-300">{icon}</div>
      <span className="text-sm text-slate-300">{title}</span>
      <b className="text-lg text-white">{value}</b>
    </div>
  );
}

function badgeClass(status: AssistantStatus) {
  return {
    sleeping: "bg-slate-700 text-white",
    listening: "bg-green-600 text-white",
    thinking: "bg-yellow-500 text-slate-950",
    speaking: "bg-blue-600 text-white",
    playing: "bg-red-600 text-white",
  }[status];
}

function orbClass(status: AssistantStatus) {
  return {
    sleeping: "bg-gradient-to-br from-blue-600 via-indigo-500 to-purple-600",
    listening: "bg-gradient-to-br from-green-500 via-emerald-400 to-cyan-400",
    thinking: "bg-gradient-to-br from-yellow-400 via-orange-400 to-amber-500",
    speaking: "bg-gradient-to-br from-cyan-400 via-blue-500 to-indigo-600",
    playing: "bg-gradient-to-br from-rose-500 via-pink-500 to-red-500",
  }[status];
}