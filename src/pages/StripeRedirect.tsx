import React, { FC } from "react";
import { useParams } from "react-router-dom";
import { StripeConnect } from "../api/api";
import { StripeOauthType } from "../types/stripe-type";
import { useQuery, UseQueryResult } from "react-query";
import { useSearchParams } from "react-router-dom";
import { useNavigate } from "react-router-dom";

const StripeRedirect: FC = () => {
  let [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  if (searchParams.get("error")) {
    return <div>{searchParams.get("error")}</div>;
  }
  const code = searchParams.get("code") || "";

  const connectStripe = async (): Promise<StripeOauthType> =>
    StripeConnect.connectStripe(code).then((res) => {
      console.log(res);
      return res;
    });

  const { data: sessionData, isLoading } = useQuery<StripeOauthType>(
    ["session"],
    connectStripe
  );

  return (
    <div>
      <h1>Stripe Redirect: Success </h1>
      <button>Go To Dashboard</button>
    </div>
  );
};

export default StripeRedirect;
