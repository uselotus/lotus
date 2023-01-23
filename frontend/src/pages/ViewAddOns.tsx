import React, { FC, useState } from "react";
import { Button } from "antd";
import { Plan } from "../api/api";
import { ArrowRightOutlined, PlusOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import {
  useQuery,
  UseQueryResult,
  useMutation,
  useQueryClient,
} from "react-query";
import { PageLayout } from "../components/base/PageLayout";
import LoadingSpinner from "../components/LoadingSpinner";
import AddOnsCard from "../components/Addons/AddonsCard/AddOnCard";
import { AddonType } from "../types/addon-type";

const ViewAddOns: FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [addOns, setAddOns] = useState<AddonType[]>([
    {
      name: "Words A-O",
      active_customers: "23",
      addon_id: "1812sffsf4abf",
      billing_frequency: "Recurring",
      price: "120.00",
      type: "flat",
    },
  ]);
  const navigateCreatePlan = () => {
    navigate("/create-addon");
  };

  return (
    <PageLayout
      title="Add-ons"
      className="text-[24px]"
      extra={[
        <Button
          onClick={navigateCreatePlan}
          type="primary"
          size="large"
          key="create-plan"
          className="hover:!bg-primary-700"
          style={{ background: "#C3986B", borderColor: "#C3986B" }}
        >
          <div className="flex items-center  justify-between text-white">
            <div>
              <PlusOutlined className="!text-white w-12 h-12 cursor-pointer" />
              Create Add-on
            </div>
            <ArrowRightOutlined className="pl-2" />
          </div>
        </Button>,
      ]}
    >
      <div className="flex flex-col">
        {addOns ? (
          <div className="grid gap-20  grid-cols-1 md:grid-cols-2 xl:grid-cols-4">
            {addOns?.map((item, key) => (
              <AddOnsCard add_on={item} key={key} />
            ))}
          </div>
        ) : (
          <div className="flex items-center justify-center">
            <div className="mt-[40%]" />
            <LoadingSpinner />
          </div>
        )}
      </div>
    </PageLayout>
  );
};

export default ViewAddOns;
