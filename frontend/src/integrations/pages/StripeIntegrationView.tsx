import React, { FC, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { useNavigate } from "react-router-dom";
import { PageLayout } from "../../components/base/PageLayout";
import { Button } from "antd";

//create FC component called StripeIntegration
const StripeIntegrationView: FC = () => {
  //create variable called {id} and set it to type string
  let { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  //create variable called [connected, setConnected] and set it to type string or boolean
  const [connected, setConnected] = useState<string | boolean>(
    "Not Yet Connected"
  );

  //create variable called returnToDashboard and set it to type void
  const returnToDashboard = () => {
    navigate(-1);
  };

  //create return statement
  return (
    <PageLayout
      title="Stripe Integration"
      extra={<button onClick={returnToDashboard}>Back to Integrations</button>}
    >
      <div className="w-6/12">
        <h2 className="text-16px mb-10">
          Charge and invoice your customers through your Stripe account
        </h2>
        <div className="grid grid-cols-2 justify-start items-center gap-6 border-2 border-solid rounded border-[#EAEAEB] px-5 py-10">
          <h3>Import Stripe Customers:"</h3>
          <Button size="large" className="w-4/12">
            Import
          </Button>
          <h3 className="mx-0">Import Stripe Payments:</h3>
          <Button
            size="large"
            className="w-4/12"
            onClick={() => console.log("click")}
          >
            Import
          </Button>
          <h3>Transfer Subscriptions:</h3>
          <Button size="large" className="w-4/12">
            Transfer
          </Button>
          <h3>Create Lotus Customers In Stripe:</h3>
          <div className="flex h-5 items-center">
            <input
              id="comments"
              aria-describedby="comments-description"
              name="comments"
              type="checkbox"
              className="h-4 w-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
            />
          </div>
        </div>
        <div className="seperator"></div>
        <div></div>
      </div>
    </PageLayout>
  );
};

export default StripeIntegrationView;
