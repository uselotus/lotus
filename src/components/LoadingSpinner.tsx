import { PropagateLoader } from "react-spinners";
function LoadingSpinner() {
  return (
    <div className="grid place-items-center justify-items-center">
      <PropagateLoader
        color="#CCA43B"
        loading={true}
        size={20}
        speedMultiplier={0.5}
      />
    </div>
  );
}
export default LoadingSpinner;
