import { useRef } from "react";
import ActivityHeatmap from "./ActivityHeatmap";
import RecentCompletions from "./RecentCompletions";
import ScrollToTopButton from "./ScrollToTopButton";

export default function ActivityView() {
  const scrollRef = useRef(null);

  return (
    <div className="scroll-pane-wrap">
      <div className="scroll-pane" ref={scrollRef}>
        <ActivityHeatmap />
        <RecentCompletions />
      </div>
      <ScrollToTopButton containerRef={scrollRef} />
    </div>
  );
}