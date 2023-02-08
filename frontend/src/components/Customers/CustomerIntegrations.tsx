/* eslint-disable no-shadow */
/* eslint-disable react/no-array-index-key */
/* eslint-disable import/prefer-default-export */
import { Avatar, Card } from "antd";

import React from "react";
import { integrationsMap } from "../../types/payment-processor-type";

type Props = {
  integrations: Record<string, string>;
};
export function CustomerIntegrations({ integrations }: Props) {
  const integrationKeys = Object.keys(integrations);
  return (
    <div className="flex items-center justify-center flex-wrap">
      {integrationKeys.map((key, index) => {
        const integration = integrations[key];
        return (
          <Card
            key={index}
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
            {Object.keys(integration).map((integrationKey, index) => (
              <p key={index}>
                <b>{integrationKey} : </b> {integration[integrationKey]}
              </p>
            ))}
          </Card>
        );
      })}
    </div>
  );
}
