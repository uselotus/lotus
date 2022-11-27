import React, { FC, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { PaymentProcessorIntegration } from "../api/api";
import {
  PaymentProcessorConnectionRequestType,
  PaymentProcessorConnectionResponseType,
  StripeConnectionRequestType,
} from "../types/payment-processor-type";
import { useQuery, UseQueryResult } from "react-query";
import { useSearchParams } from "react-router-dom";
import { useNavigate } from "react-router-dom";
import { Button } from "antd";

const StripeRedirect: FC = () => {
  let [searchParams, setSearchParams] = useSearchParams();
  const [connected, setConnected] = useState<string | boolean>(
    "Not Yet Connected"
  );
  const navigate = useNavigate();

  const code = searchParams.get("code") || "";

  const request_data: StripeConnectionRequestType = {
    authorization_code: code,
  };

  const pp_info: PaymentProcessorConnectionRequestType = {
    payment_processor: "stripe",
    data: request_data,
  };
  useEffect(() => {
    if (code !== "") {
      PaymentProcessorIntegration.connectPaymentProcessor(pp_info)
        .then((data: PaymentProcessorConnectionResponseType) => {
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
    <div className="flex flex-col items-center justify-center h-full">
      <h1>Stripe Redirect: {connected} </h1>
      <Button onClick={returnToDashboard}>Go To Dashboard</Button>
    </div>
  );
};

export default StripeRedirect;
