export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <div className="text-center">
        <h1 className="text-4xl font-bold mb-4">CloudWaste</h1>
        <p className="text-xl text-gray-600 mb-8">
          Detect and identify orphaned cloud resources
        </p>
        <div className="space-x-4">
          <a
            href="/login"
            className="inline-block px-6 py-3 bg-primary text-white rounded-lg hover:bg-blue-600 transition"
          >
            Get Started
          </a>
          <a
            href="/api/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block px-6 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
          >
            API Docs
          </a>
        </div>
      </div>
    </main>
  );
}
