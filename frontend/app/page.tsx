export default function Page() {
  return (
    <main style={{display:'grid', gridTemplateColumns:'1fr 1.2fr', gap:16, padding:24}}>
      <section>
        <h1>Ask our AI anything</h1>
        {/* chat input + answers go here */}
      </section>
      <section>
        <h2>Property cards & map</h2>
        {/* cards + map placeholder */}
      </section>
    </main>
  );
}
