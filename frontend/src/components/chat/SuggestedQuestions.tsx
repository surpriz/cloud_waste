/**
 * SuggestedQuestions component - Shows suggested questions to ask
 */

"use client";

import { Lightbulb } from "lucide-react";

interface SuggestedQuestionsProps {
  onSelect: (question: string) => void;
}

const SUGGESTED_QUESTIONS = [
  "Quelles sont mes ressources les plus coûteuses?",
  "Résume mes derniers scans AWS",
  "Comment réduire mes coûts EBS?",
  "Pourquoi mes Load Balancers sont détectés?",
  "Quels sont les quick wins pour économiser de l'argent?",
  "Explique-moi les risques de suppression",
];

export function SuggestedQuestions({ onSelect }: SuggestedQuestionsProps) {
  return (
    <div className="flex flex-col items-center justify-center h-full p-8 text-center">
      <div className="mb-6">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-600/20 mb-4">
          <Lightbulb className="w-8 h-8 text-blue-400" />
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">
          FinOps AI Assistant
        </h2>
        <p className="text-gray-400 max-w-md">
          Ask me anything about your cloud resources, cost optimization, or scan results.
        </p>
      </div>

      <div className="w-full max-w-2xl">
        <p className="text-sm text-gray-500 mb-3 font-medium">
          Suggested questions:
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {SUGGESTED_QUESTIONS.map((question, index) => (
            <button
              key={index}
              onClick={() => onSelect(question)}
              className="text-left p-4 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white transition-colors border border-gray-700 hover:border-blue-500"
            >
              <div className="flex items-start gap-2">
                <span className="text-blue-400 mt-1">→</span>
                <span className="text-sm">{question}</span>
              </div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
