import React, { FC, useEffect, useState } from "react";
import { Avatar, Divider, List, Skeleton, Button, Card } from "antd";
import InfiniteScroll from "react-infinite-scroll-component";
import { Plan } from "../api/api";
import { PlanType } from "../types/plan-type";
import PlanDisplayBasic from "../components/PlanDisplayBasic";
import { useNavigate } from "react-router-dom";
import { toast } from "react-toastify";
import {
  useQuery,
  UseQueryResult,
  useMutation,
  useQueryClient,
} from "react-query";

const ViewPlans: FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const navigateCreatePlan = () => {
    navigate("/create-plan");
  };

  const {
    data: plans,
    isLoading,
    isError,
  }: UseQueryResult<PlanType[]> = useQuery<PlanType[]>(["plan_list"], () =>
    Plan.getPlans().then((res) => {
      return res;
    })
  );

  const mutation = useMutation((post: string) => Plan.deletePlan(post), {
    onSuccess: () => {
      toast.success("Successfully deleted Plan");
      queryClient.invalidateQueries(["plan_list"]);
    },

    onError: (e) => {
      toast.error("Error deleting plan");
    },
  });

  const deletePlan = (billing_plan_id: string) => {
    mutation.mutate(billing_plan_id);
  };

  return (
    <div>
      <div className="flex flex-row w-full">
        <h1 className="text-3xl font-main">Plans</h1>
        <Button
          type="primary"
          className="ml-auto bg-info"
          onClick={navigateCreatePlan}
        >
          Create Plan
        </Button>
      </div>
      <br />
      <div
        id="scrollableDiv"
        style={{
          overflow: "auto",
          padding: "0 16px",
        }}
      >
        <List
          bordered={false}
          dataSource={plans}
          className="w-full"
          renderItem={(item) => (
            <List.Item key={item.name}>
              <PlanDisplayBasic plan={item} deletePlan={deletePlan} />
            </List.Item>
          )}
        />
      </div>
    </div>
  );
};

export default ViewPlans;
