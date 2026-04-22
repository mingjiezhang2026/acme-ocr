import { useEffect, useState } from "react";
import { listenBootstrapProgress } from "../lib/tauri";
import type { BootstrapProgress } from "../lib/types";

const initialProgress: BootstrapProgress = {
  stage: "NOT_INITIALIZED",
  message: "等待安装检查",
  progress: 0,
};

export function useBootstrapProgress() {
  const [progress, setProgress] = useState<BootstrapProgress>(initialProgress);

  useEffect(() => {
    let mounted = true;
    let cleanup: (() => void) | undefined;

    void listenBootstrapProgress((next) => {
      if (mounted) {
        setProgress(next);
      }
    }).then((unlisten) => {
      cleanup = unlisten;
    });

    return () => {
      mounted = false;
      cleanup?.();
    };
  }, []);

  return { progress, setProgress };
}

