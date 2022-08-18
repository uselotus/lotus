import React, { FC, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { StripeConnect } from "../api/api";
import { StripeOauthType } from "../types/stripe-type";
import { useQuery, UseQueryResult } from "react-query";
import { useSearchParams } from "react-router-dom";
import { useNavigate } from "react-router-dom";

const StripeRedirect: FC = () => {
  let [searchParams, setSearchParams] = useSearchParams();
  const [connected, setConnected] = useState<string | boolean>(
    "Not Yet Connected"
  );
  const navigate = useNavigate();

  const code = searchParams.get("code") || "";

  useEffect(() => {
    if (code !== "") {
      StripeConnect.connectStripe(code)
        .then((data) => {
          setConnected(data.success);
        })
        .catch((error) => {
          setConnected(error.response.data.details);
        });
    }
  }, []);
  if (searchParams.get("error")) {
    return <div>{searchParams.get("error")}</div>;
  }
  const returnToDashboard = () => {
    navigate("/dashboard");
  };

  return (
    <div>
      <h1>Stripe Redirect: {connected} </h1>
      <button onClick={returnToDashboard}>Go To Dashboard</button>
    </div>
  );
};

export default StripeRedirect;
