function createShortenedText(plan: string) {
  length = plan.split("").length;
  let front = plan.split("").splice(0, 4);
  let back = plan.split("").slice(length - 4);

  return `${front.join("")}...${back.join("")}`;
}
export default createShortenedText;
