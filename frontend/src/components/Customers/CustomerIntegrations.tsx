import { Avatar, Card } from "antd";
// @ts-ignore
import React from "react";
import { integrationsMap } from "../../types/payment-processor-type";

type Props = {
  integrations: Object;
};
export const CustomerIntegrations = ({ integrations }: Props) => {
  const integrationKeys = Object.keys(integrations);
  return (
    <div className="flex items-center justify-center flex-wrap">
      {integrationKeys.map((key) => {
        const integration = integrations[key];
        return (
          <Card
            className="w-4/12"
            style={{
              boxShadow: "0 2px 4px 0 #a8a8a833",
              margin: "15px",
            }}
            title={
              <div className="flex items-center">
                <Avatar shape="square" src={integrationsMap.stripe.icon} />
                <div className="capitalize font-bold pl-4 text-2xl text-main">
                  {key}
                </div>
              </div>
            }
            size="small"
          >
            {Object.keys(integration).map((integrationKey) => (
              <p>
                <b>{integrationKey} : </b> {integration[integrationKey]}
              </p>
            ))}
          </Card>
        );
      })}
    </div>
  );
};
