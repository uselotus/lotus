import capitalize from "./capitalize";

const removeUnderscore = (str: string) => {
  if (str.includes("_")) {
    return str
      .split("_")
      .map((el) => capitalize(el))
      .join(" ");
  }
  return str;
};
export default removeUnderscore;
