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
  const [message, setMessage] = useState("Say Riko to wake me");
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
        return "Say “Riko” to wake me";
      case "listening":
        return "I’m listening";
      case "thinking":
        return "Thinking...";
      case "speaking":
        return "Speaking...";
      case "playing":
        return "Playing media";
      default:
        return "Riko AI Assistant";
    }
  }, [status]);

  return (
    <main className="min-h-screen bg-[#050816] flex items-center justify-center overflow-hidden">
      <div className="relative aspect-square h-[min(100vw,100vh,1080px)] w-[min(100vw,100vh,1080px)] overflow-hidden rounded-full border border-white/10 bg-[radial-gradient(circle_at_top,#132a57_0%,#081124_45%,#020617_100%)] shadow-[0_0_60px_rgba(0,0,0,0.45)]">
        {/* ambient background */}
        <div className="absolute inset-0">
          <div className="absolute -top-[8%] left-1/2 h-[34%] w-[34%] -translate-x-1/2 rounded-full bg-cyan-500/20 blur-3xl" />
          <div className="absolute bottom-[13%] left-[18%] h-[22%] w-[22%] rounded-full bg-fuchsia-500/10 blur-3xl" />
          <div className="absolute right-[17%] top-[18%] h-[26%] w-[26%] rounded-full bg-blue-500/10 blur-3xl" />
          <div className="absolute inset-0 bg-[linear-gradient(to_bottom,rgba(255,255,255,0.03),transparent_20%,transparent_80%,rgba(255,255,255,0.03))]" />
        </div>

        {/* splash */}
        {showSplash && (
          <button
            onClick={() => setShowSplash(false)}
            className="absolute inset-0 z-30 flex flex-col items-center justify-center rounded-full bg-[radial-gradient(circle_at_center,rgba(10,25,50,1),rgba(2,6,23,1))] px-[18%] text-white"
          >
            <div className="relative flex items-center justify-center">
              <div className="absolute h-[24vw] max-h-64 min-h-36 w-[24vw] max-w-64 min-w-36 rounded-full border border-cyan-400/30 animate-[spin_12s_linear_infinite]" />
              <div className="absolute h-[30vw] max-h-80 min-h-44 w-[30vw] max-w-80 min-w-44 rounded-full border border-fuchsia-400/20 animate-[spin_18s_linear_infinite_reverse]" />
              <div className="absolute h-[20vw] max-h-52 min-h-32 w-[20vw] max-w-52 min-w-32 rounded-full bg-cyan-400/15 blur-2xl animate-pulse" />
              <div className="relative grid h-[15vw] max-h-40 min-h-24 w-[15vw] max-w-40 min-w-24 place-items-center rounded-full bg-gradient-to-br from-cyan-400 via-blue-500 to-fuchsia-500 shadow-[0_0_60px_rgba(59,130,246,0.55)]">
                <div className="grid h-[10vw] max-h-28 min-h-16 w-[10vw] max-w-28 min-w-16 place-items-center rounded-full bg-slate-950/80">
                  <Sparkles className="h-[42%] w-[42%]" />
                </div>
              </div>

              <div className="absolute -left-[34%] top-[22%] h-3 w-3 rounded-full bg-cyan-300 animate-bounce" />
              <div className="absolute -right-[32%] bottom-[18%] h-4 w-4 rounded-full bg-fuchsia-300 animate-pulse" />
              <div className="absolute left-[18%] -top-[28%] h-2.5 w-2.5 rounded-full bg-blue-300 animate-ping" />
            </div>

            <h1 className="mt-[7%] text-center text-[clamp(2rem,5vw,3.25rem)] font-extrabold tracking-wide">
              Welcome to Riko
            </h1>
            <p className="mt-3 max-w-[34rem] text-center text-[clamp(0.95rem,2vw,1.25rem)] text-slate-300">
              Your smart voice assistant for media, search, and conversation.
            </p>

            <div className="mt-[6%] rounded-full border border-cyan-400/30 bg-white/5 px-6 py-3 text-sm text-slate-300">
              Tap anywhere to continue
            </div>
          </button>
        )}

        {/* main content */}
        <div className="relative z-10 mx-auto flex h-full w-[76%] max-w-[820px] flex-col items-center px-2 py-[8.5%] text-center text-white">
          {/* header */}
          <div className="flex w-full flex-col items-center gap-4">
            <div>
              <h1 className="text-[clamp(1.45rem,3.4vw,2.45rem)] font-bold tracking-wide">Riko AI Assistant</h1>
              <p className="mt-1 text-[clamp(0.78rem,1.35vw,0.95rem)] text-slate-300">
                Circular smart display
              </p>
            </div>

            <div className="flex max-w-full flex-wrap items-center justify-center gap-3">
              <div
                className={`h-3.5 w-3.5 rounded-full ${
                  wsConnected ? "bg-green-400 shadow-[0_0_16px_rgba(74,222,128,0.8)]" : "bg-red-400 shadow-[0_0_16px_rgba(248,113,113,0.8)]"
                }`}
              />
              <span className="text-sm font-medium text-slate-200">
                {wsConnected ? "Connected" : "Disconnected"}
              </span>
              <span
                className={`rounded-full px-4 py-2 text-xs font-bold tracking-wider ${badgeClass(
                  status
                )}`}
              >
                {status.toUpperCase()}
              </span>
            </div>
          </div>

          {/* center */}
          <section className="flex min-h-0 flex-1 flex-col items-center justify-center">
            <div className="relative flex items-center justify-center">
              {/* outer animated waves */}
              {(status === "listening" || status === "speaking") && (
                <>
                  <div className="absolute h-[28vw] max-h-72 min-h-44 w-[28vw] max-w-72 min-w-44 rounded-full border border-cyan-400/25 animate-ping" />
                  <div className="absolute h-[34vw] max-h-[22rem] min-h-52 w-[34vw] max-w-[22rem] min-w-52 rounded-full border border-cyan-300/15 animate-pulse" />
                </>
              )}

              {status === "thinking" && (
                <>
                  <div className="absolute h-[28vw] max-h-72 min-h-44 w-[28vw] max-w-72 min-w-44 rounded-full border border-yellow-400/25 animate-pulse" />
                  <div className="absolute h-[34vw] max-h-[22rem] min-h-52 w-[34vw] max-w-[22rem] min-w-52 rounded-full border border-orange-300/15 animate-[spin_8s_linear_infinite]" />
                </>
              )}

              <div
                className={`relative grid h-[27vw] max-h-72 min-h-40 w-[27vw] max-w-72 min-w-40 place-items-center rounded-full shadow-[0_0_90px_rgba(59,130,246,0.45)] transition-all duration-500 ${orbClass(
                  status
                )} ${status === "speaking" ? "animate-pulse" : ""}`}
              >
                <div className="grid h-[62%] w-[62%] place-items-center rounded-full border border-white/10 bg-slate-950/75 backdrop-blur-xl">
                  {status === "sleeping" && <Moon className="h-[42%] w-[42%]" />}
                  {status === "listening" && <Mic className="h-[42%] w-[42%]" />}
                  {status === "thinking" && <Brain className="h-[42%] w-[42%]" />}
                  {status === "speaking" && <Volume2 className="h-[42%] w-[42%]" />}
                  {status === "playing" && <Music className="h-[42%] w-[42%]" />}
                </div>
              </div>

              {/* floating particles */}
              <div className="absolute -left-[24%] top-[12%] h-4 w-4 rounded-full bg-cyan-300/80 animate-bounce" />
              <div className="absolute -right-[20%] top-[26%] h-3 w-3 rounded-full bg-fuchsia-300/80 animate-ping" />
              <div className="absolute left-[12%] -bottom-[14%] h-3.5 w-3.5 rounded-full bg-blue-300/80 animate-pulse" />
              <div className="absolute right-[14%] -bottom-[16%] h-2.5 w-2.5 rounded-full bg-cyan-200/80 animate-bounce" />
            </div>

            <h2 className="mt-[6%] max-w-full text-balance text-[clamp(1.9rem,4.8vw,3.45rem)] font-bold leading-tight">{titleText}</h2>
            <p className="mt-3 max-w-[34rem] text-balance text-[clamp(1rem,2.2vw,1.35rem)] text-slate-300">{message}</p>

            <div className="mt-[6%] grid w-full grid-cols-3 gap-3">
              <InfoCard
                icon={<Mic className="h-6 w-6" />}
                title="Microphone"
                value={wsConnected ? "Ready" : "Offline"}
              />
              <InfoCard
                icon={<Volume2 className="h-6 w-6" />}
                title="Speaker"
                value="Ready"
              />
              <InfoCard
                icon={<Play className="h-6 w-6" />}
                title="Media"
                value="YouTube"
              />
            </div>
          </section>

          {/* footer */}
          <footer className="w-[86%] rounded-full border border-white/10 bg-slate-950/40 px-7 py-4 backdrop-blur-md">
            <p className="text-[clamp(0.9rem,1.8vw,1.05rem)] text-slate-200">
              <span className="font-semibold text-cyan-300">Try:</span>{" "}
              “Riko, play Believer on YouTube”
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
    <div className="flex min-w-0 flex-col items-center gap-2 rounded-[18px] border border-white/10 bg-white/5 px-3 py-4 text-center backdrop-blur-md">
      <div className="text-cyan-300">{icon}</div>
      <span className="text-sm text-slate-300">{title}</span>
      <b className="max-w-full truncate text-[clamp(0.95rem,1.8vw,1.15rem)] text-white">{value}</b>
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
