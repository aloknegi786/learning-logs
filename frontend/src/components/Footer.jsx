export default function Footer() {
  return (
    <footer className="app-footer">
      <span>learning log — built for interview prep, one day at a time.</span>
      <span className="app-footer-dot">·</span>
      <span>{new Date().getFullYear()}</span>
    </footer>
  );
}
