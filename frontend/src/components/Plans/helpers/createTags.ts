export const createTags = (tag: string) => {
  const tagList = [
    {
      tag_color: "bg-emerald-600",
      tag_hex: "#065F46",
      tag_name: "Documentation",
    },
    {
      tag_color: "bg-emerald",
      tag_hex: "#A7F3D0",
      tag_name: "",
    },
    {
      tag_color: "bg-indigo-600",
      tag_hex: "#4F46E5",
      tag_name: "",
    },
    {
      tag_color: "bg-orange-400",
      tag_hex: "#FB923C",
      tag_name: "",
    },
    {
      tag_color: "bg-blue-600",
      tag_hex: "#2563eb",
      tag_name: "",
    },
    {
      tag_color: "bg-fuschia-500",
      tag_hex: "#D946EF",
      tag_name: "",
    },
    {
      tag_color: "bg-cyan-500",
      tag_hex: "#06B6D4",
      tag_name: "",
    },
    {
      tag_color: "bg-violet-300",
      tag_hex: "#c4b5fd",
      tag_name: "",
    },
    {
      tag_color: "bg-rose-800",
      tag_hex: "#9F1239",
      tag_name: "",
    },
    {
      tag_color: "bg-rose-400",
      tag_hex: "#fb7185",
      tag_name: "",
    },
  ];
  const randomTag = tagList[Math.floor(Math.random() * tagList.length)];
  randomTag.tag_name = tag;
  return randomTag;
};
export default createTags;
