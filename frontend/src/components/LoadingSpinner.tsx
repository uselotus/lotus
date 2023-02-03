import { PropagateLoader } from "react-spinners";
import React from "react";

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center">
      <PropagateLoader
        color="#CCA43B"
        loading
        size={20}
        speedMultiplier={0.5}
      />
    </div>
  );
}
export default LoadingSpinner;
