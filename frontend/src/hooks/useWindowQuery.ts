import { useEffect, useState } from "react";

const useMediaQuery = () => {
  const [windowWidth, setWindowWidth] = useState(() => window.innerWidth);

  useEffect(() => {
    const resizeHandler = () => {
      setWindowWidth(window.innerWidth);
    };
    window.addEventListener("resize", resizeHandler);
    return () => window.removeEventListener("resize", resizeHandler);
  }, [windowWidth]);

  return windowWidth;
};

export default useMediaQuery;
