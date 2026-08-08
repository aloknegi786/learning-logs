import { useEffect, useState } from "react";
import { ArrowUp } from "lucide-react";

/**
 * Pass a containerRef to scroll a specific box (a .scroll-pane) — used on
 * desktop where that box has its own internal scrollbar. Omit it to scroll
 * the whole window instead — used for mobile/tablet's single page scroll.
 */
export default function ScrollToTopButton({ containerRef, threshold = 240 }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const target = containerRef?.current || window;

    function handleScroll() {
      const y = containerRef?.current ? containerRef.current.scrollTop : window.scrollY;
      setVisible(y > threshold);
    }

    target.addEventListener("scroll", handleScroll, { passive: true });
    return () => target.removeEventListener("scroll", handleScroll);
  }, [containerRef, threshold]);

  function scrollToTop() {
    if (containerRef?.current) {
      containerRef.current.scrollTop = 0; // instant jump, no easing
    } else {
      window.scrollTo(0, 0);
    }
  }

  if (!visible) return null;

  return (
    <button
      className={`scroll-top-btn ${containerRef ? "pane" : "fixed"}`}
      onClick={scrollToTop}
      aria-label="Scroll to top"
    >
      <ArrowUp size={18} strokeWidth={2.5} />
    </button>
  );
}
