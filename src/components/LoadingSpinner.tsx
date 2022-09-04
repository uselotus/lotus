import { HashLoader } from "react-spinners";
function LoadingSpinner() {
  return (
    <div className="grid place-items-center justify-items-center">
      <HashLoader color="#CCA43B" loading={true} size={50} />
    </div>
  );
}
export default LoadingSpinner;
