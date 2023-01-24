function createShortenedText(plan: string, isXL: boolean) {
  length = plan.split("").length;
  const front = plan.split("").splice(0, 4);
  const back = isXL
    ? plan.split("").slice(length - 11)
    : plan.split("").slice(length - 8);

  return `${front.join("")}...${back.join("")}`;
}
export default createShortenedText;
