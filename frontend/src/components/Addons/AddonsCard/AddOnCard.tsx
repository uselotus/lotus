import React, { FC, useRef } from "react";
import { Typography } from "antd";
import { useMutation, useQueryClient } from "react-query";
import { Plan } from "../../../api/api";
import { useNavigate } from "react-router-dom";
import CopyText from "../../base/CopytoClipboard";
import createShortenedText from "../../../helpers/createShortenedText";
import capitalize from "../../../helpers/capitalize";
import useMediaQuery from "../../../hooks/useWindowQuery";
import { AddOnType } from "../../../types/add-on-type";

interface AddOnCardProps {
  add_on: AddOnType;
}

const AddOnsCard: FC<AddOnCardProps> = ({ add_on }) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const windowWidth = useMediaQuery();
  const inputRef = useRef<HTMLInputElement | null>(null!);
  //   const mutation = useMutation(
  //     (plan_id: string) =>
  //       Plan.updatePlan(plan_id, {
  //         plan_name: add_on.plan_name,
  //         status: "archived",
  //       }),
  //     {
  //       onSuccess: () => {
  //         queryClient.invalidateQueries("plan_list");

  //         toast.success("Plan archived");
  //       },
  //     }
  //   );

  //   const planMenu = (
  //     <Menu>
  //       <Menu.Item
  //         key="1"
  //         onClick={() => mutation.mutate(add_on.plan_id)}
  //         disabled={add_on.active_subscriptions > 0}
  //       >
  //         <div className="planMenuArchiveIcon">
  //           <div>
  //             <DeleteOutlined />
  //           </div>
  //           <div className="archiveLabel">Archive</div>
  //         </div>
  //       </Menu.Item>
  //     </Menu>
  //   );

  const goToAddOnDetail = () => {
    navigate("/add_on/" + add_on.addon_id);
  };

  return (
    <div
      className="min-h-[200px]  min-w-[246px] p-6 cursor-pointer  rounded-sm bg-card  shadow-lg hover:shadow-neutral-400"
      onClick={goToAddOnDetail}
      aria-hidden
    >
      <Typography.Title className="pt-4 flex font-alliance" level={2}>
        <span>{add_on.name}</span>
        {/* <span
          className="ml-auto"
          onClick={(e) => e.stopPropagation()}
          aria-hidden
        >
          <Dropdown overlay={planMenu} trigger={["click"]}>
            <Button
              type="text"
              size="small"
              onClick={(e) => e.preventDefault()}
            >
              <MoreOutlined />
            </Button>
          </Dropdown>
        </span> */}
      </Typography.Title>

      <div>
        <div>
          <div className="mb-2">
            <div className="pr-1 font-normal font-alliance not-italic whitespace-nowrap  text-darkgold">
              Total Active Customer: {add_on.active_customers}
            </div>
            <div className=" w-full h-[1.5px] mt-6 bg-card-divider" />
          </div>

          <div className="flex items-center text-card-text justify-between gap-2 mb-1">
            <div className=" font-normal whitespace-nowrap leading-4">
              Add-On ID
            </div>
            <div className="flex gap-1 text-card-grey font-menlo">
              {" "}
              <div>
                {createShortenedText(add_on.addon_id, windowWidth >= 2500)}
              </div>
              <CopyText showIcon onlyIcon textToCopy={add_on.addon_id} />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between text-card-text gap-2 mb-1">
          <div className="font-normal whitespace-nowrap leading-4">Type</div>
          <div className="text-card-grey font-main">{add_on.type}</div>
        </div>

        <div className="flex items-center justify-between text-card-text gap-2 mb-1">
          <div className="font-normal whitespace-nowrap leading-4">Price</div>
          <div className="text-card-grey font-main">
            {" "}
            {add_on.price.includes(".00") ? `$${add_on.price}` : add_on.price}
          </div>
        </div>

        <div className="flex items-center text-card-text justify-between gap-2 mb-1">
          <div className="font-normal text-card-text whitespace-nowrap leading-4xs">
            Billing Frequency
          </div>
          <div className="text-card-grey font-main">
            {" "}
            {capitalize(add_on.billing_frequency)}
          </div>
        </div>
      </div>
    </div>
  );
};
export default AddOnsCard;
