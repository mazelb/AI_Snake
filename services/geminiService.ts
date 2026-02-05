import { GoogleGenAI, Type } from "@google/genai";
import { Point, LevelConfig } from "../types";
import { GRID_SIZE } from "../constants";

// Initialize the Gemini AI client
// We create the instance lazily or on demand to ensure we catch the environment variable at runtime
const getAIClient = () => {
  const apiKey = process.env.API_KEY;
  if (!apiKey) {
    throw new Error("API Key is missing. Please set process.env.API_KEY.");
  }
  return new GoogleGenAI({ apiKey });
};

export const generateLevel = async (prompt: string): Promise<LevelConfig> => {
  const ai = getAIClient();

  const systemInstruction = `
    You are a game level designer for a Snake game.
    The grid size is ${GRID_SIZE}x${GRID_SIZE} (coordinates 0 to ${GRID_SIZE - 1}).
    You must generate a list of 'walls' (obstacles) based on the user's description.
    Ensure the walls do not completely block the board or make it impossible.
    Do NOT place walls in the center 3x3 area (coordinates 9,9 to 11,11) as that is the spawn point.
    Be creative with patterns (mazes, shapes, letters) if requested.
  `;

  try {
    const response = await ai.models.generateContent({
      model: "gemini-3-flash-preview",
      contents: `Generate a level layout matching this description: "${prompt}"`,
      config: {
        systemInstruction: systemInstruction,
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            levelName: { type: Type.STRING, description: "A creative name for the level" },
            description: { type: Type.STRING, description: "Short description of the layout" },
            walls: {
              type: Type.ARRAY,
              items: {
                type: Type.OBJECT,
                properties: {
                  x: { type: Type.INTEGER },
                  y: { type: Type.INTEGER }
                },
                required: ["x", "y"]
              }
            }
          },
          required: ["levelName", "walls"]
        }
      }
    });

    const jsonText = response.text;
    if (!jsonText) {
      throw new Error("No response from AI");
    }

    const data = JSON.parse(jsonText);

    // Validate coordinates to be within grid bounds
    const validWalls: Point[] = (data.walls || []).filter((w: Point) => 
      w.x >= 0 && w.x < GRID_SIZE && w.y >= 0 && w.y < GRID_SIZE
    );

    return {
      name: data.levelName || "AI Generated Level",
      description: data.description || "A custom generated map.",
      walls: validWalls
    };

  } catch (error) {
    console.error("Error generating level:", error);
    // Return a fallback empty level or rethrow depending on desired UX
    throw error;
  }
};