/**
 * SuggestedQuestions component - Shows suggested questions to ask
 */

"use client";

import { Lightbulb, Shield, Brain, Zap } from "lucide-react";

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
    <div className="flex flex-col items-center justify-center h-full p-8 overflow-y-auto">
      <div className="w-full max-w-3xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-600/20 mb-4">
            <Lightbulb className="w-8 h-8 text-blue-400" />
          </div>
          <h2 className="text-2xl font-bold text-white mb-2">
            Assistant FinOps IA
          </h2>
          <p className="text-gray-400 max-w-lg mx-auto">
            Posez-moi vos questions sur vos ressources cloud, l'optimisation des coûts ou vos résultats de scan.
          </p>
        </div>

        {/* Info card */}
        <div className="bg-gray-800/50 border border-gray-700 rounded-xl p-6 mb-8">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Brain className="w-5 h-5 text-blue-400" />
            Comment ça marche ?
          </h3>

          <div className="space-y-4">
            <div className="flex gap-3">
              <div className="flex-shrink-0 mt-1">
                <Zap className="w-5 h-5 text-green-400" />
              </div>
              <div>
                <p className="text-sm text-gray-300 font-medium mb-1">Analyse intelligente de vos données</p>
                <p className="text-sm text-gray-400">
                  L'assistant analyse automatiquement vos scans, ressources orphelines et coûts pour vous fournir des réponses personnalisées.
                </p>
              </div>
            </div>

            <div className="flex gap-3">
              <div className="flex-shrink-0 mt-1">
                <Shield className="w-5 h-5 text-blue-400" />
              </div>
              <div>
                <p className="text-sm text-gray-300 font-medium mb-1">100% sécurisé et confidentiel</p>
                <p className="text-sm text-gray-400">
                  Vos données restent dans votre infrastructure. L'IA utilise uniquement les informations de vos scans pour générer des recommandations.
                </p>
              </div>
            </div>

            <div className="bg-blue-900/20 border border-blue-800/30 rounded-lg p-3 mt-4">
              <p className="text-xs text-blue-300">
                💡 <strong>Astuce :</strong> Posez des questions en français ou en anglais. L'assistant comprend le contexte technique et s'adapte à votre niveau.
              </p>
            </div>
          </div>
        </div>

        {/* Suggested questions */}
        <div>
          <p className="text-sm text-gray-400 mb-4 font-medium">
            Questions suggérées pour commencer :
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
    </div>
  );
}
