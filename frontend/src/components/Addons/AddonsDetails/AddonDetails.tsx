import React, { FC, Fragment, useState } from "react";

import { Button, Typography } from "antd";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "react-query";
import { PageLayout } from "../../base/PageLayout";
import { AddOn } from "../../../api/api";
import LoadingSpinner from "../../LoadingSpinner";
import { AddOnType } from "../../../types/addon-type";
import AddOnInfo from "./AddOnInfo";
import AddOnComponents from "./AddOnComponents";
import AddOnFeatures from "./AddOnFeatures";
import { components } from "../../../gen-types";

type AddOnDetailsParams = {
  addOnId: string;
};

const AddOnDetails: FC = () => {
  const navigate = useNavigate();

  const { addOnId } = useParams<AddOnDetailsParams>();
  const queryClient = useQueryClient();
  const [add_on, setAddOn] = useState<AddOnType>({
    addon_name: "Unlimited Text Add-On",
    description: "Lorem Ipsum Dolores stuff",
    flat_rate: 49.0,
    addon_id: "asdwwwew",
    currency: {
      symbol: "$",
      name: "USD",
      code: "USD",
    },
    billing_frequency: "one_time",
    addon_type: "flat_fee",
    invoice_when: "On Attach",
    active_instances: 23,
    components: [],
    features: [],
  });
  const {
    data: addon,
    isLoading,
    isError,
    refetch,
  } = useQuery<components["schemas"]["AddOnDetail"]>(
    ["addon_detail", addOnId],
    () => AddOn.getAddOn(addOnId as string).then((res) => res),
    { refetchOnMount: "always" }
  );

  return (
    <>
      {isLoading && (
        <div className="flex h-full">
          <div className="m-auto">
            <LoadingSpinner />
          </div>
        </div>
      )}
      {isError && (
        <div className="flex flex-col items-center justify-center h-full">
          <h2 className="4">Could Not Load Add-On</h2>
          <Button type="primary" onClick={() => navigate(-1)}>
            Go Back
          </Button>
        </div>
      )}
      {addon && (
        <div>
          <PageLayout
            title={
              <div>
                <div className="font-alliance">{addon.addon_name}</div>
                <div className="text-base Inter text-card-grey ml-2">
                  {addon.addon_description}
                </div>
              </div>
            }
            hasBackButton
            aboveTitle
            backButton={
              <div>
                <Button
                  onClick={() => navigate(-1)}
                  type="primary"
                  size="large"
                  key="create-custom-plan"
                  style={{
                    background: "#F5F5F5",
                    borderColor: "#F5F5F5",
                  }}
                >
                  <div className="flex items-center justify-between text-black">
                    <div>&larr; Go back</div>
                  </div>
                </Button>
              </div>
            }
          />
          <div className="mx-10">
            <div className="bg-white mb-6 flex flex-col py-4 px-10 rounded-lg space-y-12">
              <div>
                <AddOnInfo addOnInfo={addon} />
              </div>

              <div className="grid gap-18 grid-cols-1  md:grid-cols-2 w-full">
                {addon?.versions[0].components.length > 0 && (
                  <AddOnComponents
                    refetch={refetch}
                    plan={addon}
                    components={addon?.versions[0].components}
                  />
                )}
                <AddOnFeatures features={addon?.versions[0].features} />
              </div>
            </div>
          </div>
          <div className="separator mt-4" />
        </div>
      )}
    </>
  );
};
export default AddOnDetails;
