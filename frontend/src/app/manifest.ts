import type { MetadataRoute } from "next";
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "GradeKade scanning desk",
    short_name: "GradeKade",
    description: "Capture paper worksheets and review grading exceptions.",
    start_url: "/scan",
    display: "standalone",
    background_color: "#f7f8f5",
    theme_color: "#1c5946",
    icons: [
      {
        src: "/scan-icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any",
      },
    ],
  };
}
