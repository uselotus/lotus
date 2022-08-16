import React, { FC } from "react";
import { useParams } from "react-router-dom";
import { StripeConnect } from "../api/api";
import { StripeOauthType } from "../types/stripe-type";
import { useQuery, UseQueryResult } from "react-query";

const StripeRedirect: FC = () => {
  let { code, error } = useParams();

  const connectStripe = async (): Promise<StripeOauthType> =>
    StripeConnect.connectStripe(code).then((res) => {
      return res;
    });

  const { data: sessionData, isLoading } = useQuery<StripeOauthType>(
    ["session"],
    connectStripe
  );

  return (
    <div>
      <h1>Stripe Redirect </h1>
      <button>Go To Dashboard {code}</button>
    </div>
  );
};

export default StripeRedirect;
